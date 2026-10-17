import asyncio
import ssl
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


class WProxy:
    def __init__(self, *args, **kwargs):
        self.host = kwargs.get('host', '0.0.0.0')
        self.port = int(kwargs.get('port', 8765))
        self.url = kwargs.get('url', '')
        target = urlsplit(self.url)
        if target.scheme not in ('ws', 'wss') or not target.netloc or target.fragment or target.query:
            raise ValueError('Specify a ws:// or wss:// upstream base URL without query or fragment')
        if not 0 <= self.port <= 65535:
            raise ValueError('Proxy port must be between 0 and 65535')
        self.ssl_cert = kwargs.get('ssl_cert')
        self.ssl_key = kwargs.get('ssl_key')
        self.extra_headers = dict(kwargs.get('extra_headers') or {})
        self.ssl_context = None
        if bool(self.ssl_cert) != bool(self.ssl_key):
            raise ValueError('Supply both the SSL certificate and key')
        if self.ssl_cert:
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.ssl_context.load_cert_chain(self.ssl_cert, keyfile=self.ssl_key)

    def load_headers_from_args(self, headers):
        for header in headers or []:
            name, separator, value = header.partition(':')
            if not separator or not name.strip() or any(char in header for char in '\r\n'):
                raise ValueError('Each HTTP header must have a name and colon, without newlines')
            self.extra_headers[name.strip()] = value.strip()

    async def _relay(self, source, destination):
        async for message in source:
            await destination.send(message)

    async def _on_connection(self, websocket):
        try:
            async with connect(self.url.rstrip('/') + websocket.request.path,
                               open_timeout=10, close_timeout=5) as upstream:
                tasks = [asyncio.create_task(self._relay(upstream, websocket)),
                         asyncio.create_task(self._relay(websocket, upstream))]
                try:
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except ConnectionClosed:
            pass  # Either peer closing ends both relay tasks.
        except (OSError, TimeoutError):
            await websocket.close(code=1011, reason='Upstream connection unavailable')

    def _response_headers(self, connection, request, response):
        response.headers.update(self.extra_headers)
        return response

    async def start(self):
        """Start inside the caller's event loop; caller owns close/wait_closed."""
        return await serve(self._on_connection, self.host, self.port,
                           ssl=self.ssl_context, process_response=self._response_headers,
                           open_timeout=10, close_timeout=5)

    async def run_async(self):
        async with await self.start() as server:
            await server.serve_forever()

    def run(self):
        asyncio.run(self.run_async())

import asyncio
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from wproxy import WProxy


class ProxyTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_proxy_relays_text_binary_path_query_and_response_headers(self):
        paths = []
        async def echo(connection):
            paths.append(connection.request.path)
            async for message in connection:
                await connection.send(message)
        async with serve(echo, '127.0.0.1', 0) as upstream:
            port = upstream.sockets[0].getsockname()[1]
            proxy = WProxy(host='127.0.0.1', port=0, url=f'ws://127.0.0.1:{port}/base')
            proxy.load_headers_from_args(['X-Synthetic: value:with:colons'])
            server = await proxy.start()
            async with server:
                proxy_port = server.sockets[0].getsockname()[1]
                async with connect(f'ws://127.0.0.1:{proxy_port}/echo?fixture=1') as client:
                    self.assertEqual(client.response.headers['X-Synthetic'], 'value:with:colons')
                    for message in ['synthetic text', b'\x00\x01binary']:
                        await client.send(message)
                        self.assertEqual(await asyncio.wait_for(client.recv(), 2), message)
            self.assertEqual(paths, ['/base/echo?fixture=1'])

    async def test_run_async_can_be_cancelled_and_releases_listener(self):
        proxy = WProxy(host='127.0.0.1', port=0, url='ws://127.0.0.1:1')
        task = asyncio.create_task(proxy.run_async())
        await asyncio.sleep(0.05)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)

    def test_invalid_configuration_and_headers_fail_before_serving(self):
        for target in ['', 'https://example.invalid', 'ws://localhost/#fragment']:
            with self.assertRaises(ValueError):
                WProxy(url=target)
        with self.assertRaises(ValueError):
            WProxy(url='ws://localhost', ssl_cert='certificate-only')
        proxy = WProxy(url='ws://localhost')
        for header in ['missing-colon', ': empty-name', 'X-Test: unsafe\r\nInjected: value']:
            with self.assertRaises(ValueError):
                proxy.load_headers_from_args([header])

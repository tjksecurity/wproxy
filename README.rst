wproxy
======

A Python 3 websocket proxy

Installing Through PyPi
=======================
::

    pip3 install wproxy

Using the library
=================
::

    from wproxy import WProxy

    this_proxy = WProxy(
        host="0.0.0.0",
        port=9002,
        url="wss://urltoproxy.com",
        ssl_cert="cert.pem", # optional
        ssl_key="priv.pem", # optional
    )

    this_proxy.run()

Running the console script
==========================
::

    wproxy --url wss://urltoproxy.com:8888 --port 9002 --headers "Sec-WebSocket-Protocol:sip" --ssl_cert fullchain1.pem --ssl_key privkey1.pem
Runtime compatibility
---------------------
Requires Python 3.11+ and websockets 17.2.x. The CLI owns its asyncio loop.
Async callers can await WProxy.start(), then close()/wait_closed() the returned server.
Run isolated regressions with: python -m unittest discover -s tests -v.

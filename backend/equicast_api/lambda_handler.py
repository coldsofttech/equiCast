"""Lambda entrypoint: wraps the Django ASGI app for API Gateway (HTTP API,
payload format 2.0) via `mangum`.

`lifespan="off"` is required — Django's ASGI handler doesn't implement the
lifespan protocol mangum otherwise tries to negotiate on cold start.
"""

from mangum import Mangum

from equicast_api.asgi import application

handler = Mangum(application, lifespan="off")

import mimetypes

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class Assets(StaticFiles):
    async def get_response(self, path, scope):
        headers = dict(scope.get("headers", []))
        accepted = headers.get(b"accept-encoding", b"").decode("latin-1").lower()
        gzip_allowed = False
        for encoding in accepted.split(","):
            parts = [part.strip() for part in encoding.split(";")]
            if parts[0] == "gzip":
                try:
                    gzip_allowed = not any(part.startswith("q=") and float(part[2:] or "0") <= 0 for part in parts[1:])
                except ValueError:
                    gzip_allowed = False
        if gzip_allowed:
            try:
                response = await super().get_response(path + ".gz", scope)
                response.headers["content-type"] = mimetypes.guess_type(path)[0] or "application/octet-stream"
                response.headers["content-encoding"] = "gzip"
                response.headers["vary"] = "Accept-Encoding"
                return response
            except HTTPException as error:
                if error.status_code != 404:
                    raise
        response = await super().get_response(path, scope)
        response.headers["vary"] = "Accept-Encoding"
        return response

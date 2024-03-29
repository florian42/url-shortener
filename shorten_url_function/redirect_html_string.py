def get_redirect_content(url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8" />
        <meta http-equiv="refresh" content="0;url='{url}'" />

        <title>Redirecting to {url}</title>
    </head>
    <body>
        Redirecting to <a href="{url}">{url}</a>.
    </body>
</html>"""

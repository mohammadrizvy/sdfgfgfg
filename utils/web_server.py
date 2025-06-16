from aiohttp import web
import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('discord')

class TranscriptWebServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.transcript_dir = Path("web_transcripts")
        self.transcript_dir.mkdir(exist_ok=True)
        # Use localhost for development, replace with your actual server IP in production
        self.base_url = f"http://localhost:{port}/view/"
        self.setup_routes()
        self.setup_middleware()
        self.access_tokens = {}  # Store valid access tokens

    def setup_middleware(self):
        @web.middleware
        async def auth_middleware(request, handler):
            # Skip auth for OPTIONS requests
            if request.method == 'OPTIONS':
                return await handler(request)

            # Check if the request is for a transcript
            if request.path.startswith('/view/'):
                # Get the access token from query parameters
                access_token = request.query.get('token')
                
                if not access_token or access_token not in self.access_tokens:
                    return web.Response(
                        text="Access denied. Invalid or missing access token.",
                        status=403
                    )

            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            return response

        self.app.middlewares.append(auth_middleware)

    def setup_routes(self):
        # Serve static files from the transcript directory
        self.app.router.add_static('/view', self.transcript_dir)
        
        # Add a route for the index page
        self.app.router.add_get('/', self.handle_index)
        
        # Add a route for transcript viewing
        self.app.router.add_get('/view/{transcript_id}', self.handle_transcript)
        
        # Handle OPTIONS requests
        self.app.router.add_options('/{tail:.*}', self.handle_options)

    async def handle_options(self, request):
        return web.Response()

    async def handle_index(self, request):
        return web.Response(text="Transcript Server Running")

    async def handle_transcript(self, request):
        transcript_id = request.match_info['transcript_id']
        transcript_path = self.transcript_dir / f"ticket_{transcript_id}.html"
        
        if transcript_path.exists():
            return web.FileResponse(transcript_path)
        else:
            return web.Response(
                text="Transcript not found",
                status=404
            )

    def generate_access_token(self, ticket_number: str) -> str:
        """Generate a unique access token for a transcript"""
        import secrets
        token = secrets.token_urlsafe(32)
        self.access_tokens[token] = {
            'ticket_number': ticket_number,
            'created_at': datetime.utcnow().isoformat()
        }
        return token

    def get_transcript_url(self, transcript_id: str, ticket_number: str) -> str:
        """Generate a secure URL for accessing a transcript"""
        token = self.generate_access_token(ticket_number)
        return f"{self.base_url}{transcript_id}?token={token}"

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Transcript web server running at http://{self.host}:{self.port}")
        return runner

    async def stop(self, runner):
        await runner.cleanup() 
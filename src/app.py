"""
Flask Application - Human Rights Education Platform
Main entry point with eager initialization
"""

from flask import Flask, render_template
from flask_cors import CORS
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app_root = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_DIR = os.path.join(app_root, '..', 'frontend', 'templates')
STATIC_DIR = os.path.join(app_root, '..', 'frontend', 'static')

# Create Flask app
app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR
)

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Print banner
print("\n" + "="*60)
print("🌍 Human Rights Education Platform")
print("="*60)
print("Server starting on http://localhost:5050")
print("\nAvailable endpoints:")
print("  GET  /api/health       - System health check")
print("  GET  /api/topics       - List available topics")
print("  POST /api/chat         - Simple RAG mode")
print("  POST /api/agent/chat   - Agent mode (autonomous)")
print("  POST /api/agent/debug  - Agent with debug info")
print("="*60 + "\n")

# ===== EAGER INITIALIZATION =====
# Initialize RAG and Agent BEFORE Flask starts
# This ensures they're ready when first request comes in

logger.info("⏳ Initializing systems (this may take 30-60 seconds)...")

# Import routes (this will trigger singleton initialization)
from src.api.routes import agent_routes

# Force initialization by calling the getter functions
try:
    logger.info("Initializing RAG system...")
    rag = agent_routes.get_rag()
    if rag:
        logger.info("✅ RAG system ready")
    else:
        logger.error("❌ RAG system failed to initialize")
except Exception as e:
    logger.error(f"❌ RAG initialization error: {e}")

try:
    logger.info("Initializing Agent system...")
    agent = agent_routes.get_agent()
    if agent:
        logger.info(f"✅ Agent ready with {len(agent.tools)} tools")
    else:
        logger.error("❌ Agent failed to initialize")
except Exception as e:
    logger.error(f"❌ Agent initialization error: {e}")

logger.info("✅ All systems initialized and ready\n")

# Register blueprints AFTER initialization
app.register_blueprint(agent_routes.bp)

# Root endpoint
@app.route('/')
def index():
    return render_template('index.html', user='Guest')
    '''{
        'message': 'Human Rights Education Platform API',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            'health': '/api/health',
            'topics': '/api/topics',
            'simple_rag': '/api/chat',
            'agent': '/api/agent/chat',
            'debug': '/api/agent/debug',
            'tools': '/api/agent/tools'
        }
    }'''

if __name__ == '__main__':
    # Verify environment
    if not os.getenv('GOOGLE_API_KEY'):
        logger.warning("⚠️  WARNING: GOOGLE_API_KEY not found in environment!")
        logger.warning("Create a .env file with: GOOGLE_API_KEY=your-key-here")
    
    print("=== URL MAP ===")
    print(app.url_map)
    print("===============")
    # Start server
    app.run(
        host='0.0.0.0',
        port=5050,
        debug=True,
        use_reloader=False  # Disable reloader to prevent double initialization
    )
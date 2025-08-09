# Admin Cockpit Application

## 🚀 Quick Start for Claude Agents

### Project Structure
```
overview/
├── Admin-Cockpit-Backend/      # Express.js API (Port 8080)
├── Admin-Cockpit-Frontend/     # Next.js 15 App (Port 3000)
├── docker-compose.yaml         # Container orchestration
├── Makefile                    # Build commands
├── CLAUDE.md                   # AI assistant instructions
└── docs/                       # Documentation
```

### Core Features
1. **Authentication** - JWT-based auth with secure cookies
2. **Summary Dashboard** - Analytics and metrics overview
3. **Administration** - User, location, and system management
4. **Credentialing** - Provider credential tracking (TO BE IMPLEMENTED)
5. **Fee Strategy** - Pivot table analysis (TO BE IMPLEMENTED)

### Quick Commands
```bash
# Local Development
make dev              # Start both frontend and backend
make backend          # Start backend only
make frontend         # Start frontend only

# Docker Development
docker-compose up     # Start all services
```

### Key Endpoints
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080/api/v1
- Health Check: http://localhost:8080/api/v1/health

### Environment Setup
1. Copy `.env.example` to `.env` in both directories
2. Set MongoDB connection string
3. Set JWT secret and other required vars

### For Detailed Setup
- See `docs/LOCAL_SETUP_GUIDE.md` for local development
- See `docs/DOCKER_GUIDE.md` for Docker setup
- See `CLAUDE.md` for AI assistant context
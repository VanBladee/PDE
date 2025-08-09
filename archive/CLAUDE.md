# CLAUDE.md - AI Assistant Context

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Project Overview

This is the Admin Cockpit application consisting of:
- **Backend**: Express.js/TypeScript API with MongoDB (port 8080)
- **Frontend**: Next.js 15 with TypeScript and Tailwind CSS (port 3000)
- **Infrastructure**: Docker Compose setup with Redis support

## 💻 Common Development Commands

### Backend (Admin-Cockpit-Backend/)
```bash
npm run dev              # Start development server with ts-node-dev
npm run dev:nodemon      # Alternative: Start with nodemon
npm run build            # Build TypeScript to dist/
npm start                # Run production build
```

### Frontend (Admin-Cockpit-Frontend/)
```bash
npm run dev              # Start Next.js dev server with Turbopack
npm run build            # Build for production
npm start                # Run production build
npm run lint             # Run Next.js linting
```

### Quick Start
```bash
# Using Make (recommended)
make dev         # Start both frontend and backend
make backend     # Backend only
make frontend    # Frontend only

# Using Docker
docker-compose up
```

## 🏗️ Architecture Overview

### Backend Structure
- **API Routes**: Versioned under `/api/v1/` with route modules for each resource
- **Controllers**: Business logic separated from routes (one controller per resource)
- **Models**: MongoDB schemas organized by database (activity/, od_live/, registry/)
- **Middleware**: Authentication (JWT) and error handling
- **Multi-Database**: Connects to multiple MongoDB databases (od_live, activity, registry)
- **Caching**: Redis integration for session management and caching

### Frontend Structure
- **App Router**: Next.js 15 app directory structure
- **UI Components**: Shadcn/ui components in components/ui/
- **Dashboard**: Main app under /dashboard with nested routes
- **State Management**: React Query for server state, Context API for auth
- **Styling**: Tailwind CSS v4 with custom components

### Authentication Flow
1. JWT-based authentication with httpOnly cookies
2. Backend middleware validates tokens
3. Frontend AuthContext manages user state
4. Protected routes use middleware.ts

### Key Dependencies
- **Backend**: Express, Mongoose, bcrypt, jsonwebtoken, ioredis, SendGrid
- **Frontend**: Next.js 15, React 19, React Query, Shadcn/ui, Recharts, date-fns

## 🔐 Environment Variables

### Backend (.env)
Required:
- MONGO_URI: MongoDB connection string
- MONGO_DB_NAME: Primary database name
- JWT_SECRET: Secret for JWT signing
- REDIS_URL: Redis connection string

Optional (for full features):
- SENDGRID_API_KEY: Email notifications
- ANTHROPIC_API_KEY: AI features
- STRIPE_SECRET_KEY: Payment processing
- AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY: Document storage

### Frontend (.env.local)
- NEXT_PUBLIC_API_URL: Backend API URL (default: http://localhost:8080)

## 🗄️ Database Schema
The app uses three MongoDB databases:
1. **registry**: Users, Organizations, Locations
2. **activity**: Analytics, AuditLogs, Jobs, ProcessedClaims
3. **od_live**: Carriers, ClaimsOutbound

## 🧪 Testing
No test commands configured yet. Consider adding:
- Jest for backend unit tests
- React Testing Library for frontend
- Cypress/Playwright for E2E tests

## ⭐ Key Features

### Current Features
1. **Authentication System** - JWT-based secure authentication
2. **Summary Dashboard** - Real-time analytics and metrics
3. **Administration Panel** - User, location, and system management

### Upcoming Features

### 1. Credentialing Page (TO BE IMPLEMENTED)
- Provider credential tracking and management
- Real-time credentialing status updates
- Bulk operations and export functionality

### 2. Fee Strategy Dashboard (TO BE IMPLEMENTED)
A data-driven tool for optimizing insurance carrier relationships.
- **Purpose**: Analyze claims data to identify unprofitable carrier relationships and negotiation opportunities
- **Default View**: Scatter plot showing most/least profitable CDT codes based on selection state
- **Dual Modes**: Toggle between Profitability Focus and Write-off Focus views
- **Smart Filtering**: Dual-sidebar navigation (Carriers → Locations) with dynamic data aggregation
- **Verdict System**: Automatic categorization (KEEP/NEGOTIATE/DROP) based on write-off % and patient volume
- **Data Source**: Currently uses comprehensive mock data; ready for real claims API integration
# Project Structure Guide

## 📁 Directory Layout

```
overview/
├── Admin-Cockpit-Backend/
│   ├── src/
│   │   ├── api/v1/routes/      # API endpoints
│   │   ├── controllers/        # Business logic
│   │   ├── models/            # MongoDB schemas
│   │   ├── middleware/        # Auth & error handling
│   │   ├── utils/             # Helper functions
│   │   ├── config/            # Configuration
│   │   └── index.ts           # Server entry point
│   ├── Dockerfile             # Container setup
│   ├── package.json           # Dependencies
│   └── tsconfig.json          # TypeScript config
│
├── Admin-Cockpit-Frontend/
│   ├── src/
│   │   ├── app/               # Next.js app router
│   │   │   ├── dashboard/     # Main application
│   │   │   │   ├── summary/   # Analytics dashboard
│   │   │   │   ├── administration/ # User/location management
│   │   │   │   ├── credentialing/ # Provider credentials (TBD)
│   │   │   │   └── fee-strategy/  # Pivot analysis (TBD)
│   │   │   └── layout.tsx     # Root layout
│   │   ├── components/        # React components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── lib/               # API clients & utilities
│   │   ├── context/           # React contexts
│   │   └── types/             # TypeScript definitions
│   ├── public/                # Static assets
│   ├── Dockerfile             # Container setup
│   ├── package.json           # Dependencies
│   └── next.config.ts         # Next.js config
│
├── docs/                      # All documentation
├── docker-compose.yaml        # Multi-container setup
├── Makefile                   # Build automation
├── CLAUDE.md                  # AI assistant context
├── README.md                  # Quick start guide
└── PROJECT_STRUCTURE.md       # This file
```

## 🔑 Key Files for Each Feature

### Authentication
- Backend: `src/controllers/auth.controller.ts`
- Frontend: `src/context/AuthContext.tsx`
- Middleware: `src/middleware/auth.middleware.ts`

### Summary Dashboard
- Page: `src/app/dashboard/summary/page.tsx`
- Component: `src/components/dashboard/summary/summary.tsx`
- API: `src/api/v1/routes/analytics.ts`

### Administration
- Users: `src/app/dashboard/administration/users/`
- Locations: `src/app/dashboard/administration/locations/`
- APIs: `users.ts`, `locations.ts`, `audit-logs.ts`

### Credentialing (TO BE IMPLEMENTED)
- Page: `src/app/dashboard/credentialing/`
- API: `src/api/v1/routes/credentialing.ts`
- Controller: `src/controllers/credentialing.controller.ts`

### Fee Strategy (TO BE IMPLEMENTED)
- Page: `src/app/dashboard/fee-strategy/`
- API: `src/api/v1/routes/fee-strategy.ts`
- Controller: `src/controllers/fee-strategy.controller.ts`

## 🗄️ Database Collections

### registry database
- users
- organizations
- locations

### activity database
- analytics
- audit_logs
- jobs
- processed_claims

### od_live database
- carriers
- claims_outbound
- PDC_fee_validation (for fee strategy)

## 🚀 Common Tasks

### Adding a New Page
1. Create page in `Frontend/src/app/dashboard/[feature]/page.tsx`
2. Add navigation link in sidebar component
3. Create API route in `Backend/src/api/v1/routes/`
4. Add controller in `Backend/src/controllers/`

### Adding an API Endpoint
1. Define route in `routes/[feature].ts`
2. Implement logic in `controllers/[feature].controller.ts`
3. Add types in `Frontend/src/types/`
4. Create API client in `Frontend/src/lib/api/`

### Environment Variables
- Backend: Copy `.env.example` to `.env`
- Frontend: Copy `.env.local.example` to `.env.local`
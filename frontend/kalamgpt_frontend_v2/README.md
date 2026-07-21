# Kalam GPT Frontend (v2.0)

Complete React frontend with authentication, routing, and chat interface.

## Features

✅ **User Authentication**
- Register with email, name, password
- OTP verification (6-digit code)
- Login with JWT token
- Session management

✅ **Protected Routes**
- Dashboard (user profile, chat history)
- Chat interface (authenticated only)
- Auto-redirect to login if token expired

✅ **Chat Interface**
- Real-time message history
- Suggested prompts
- Typing indicators
- Quote carousel
- Mobile responsive

✅ **Security**
- JWT token stored in localStorage
- Authorization headers on all API calls
- Protected route wrapper component

## File Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── pages/
│   │   ├── RegisterPage.jsx
│   │   ├── OTPPage.jsx
│   │   ├── LoginPage.jsx
│   │   ├── DashboardPage.jsx
│   │   └── ChatPage.jsx
│   ├── context/
│   │   └── AuthContext.jsx
│   ├── components/
│   │   └── ProtectedRoute.jsx
│   ├── App.jsx
│   ├── index.js
│   └── index.css
├── package.json
└── .gitignore
```

## Setup Instructions

### Prerequisites
- Node.js v18+ and npm v10+
- Backend running on http://localhost:5000

### Installation

```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

The app will open at **http://localhost:3000**

## API Endpoints Used

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/auth/register` | POST | Create new account |
| `/api/auth/verify-otp` | POST | Verify OTP code |
| `/api/auth/login` | POST | Login with credentials |
| `/api/generate` | POST | Send chat message (requires auth) |
| `/api/chat/history` | GET | Get user's chat history |

## Environment Variables

Create `.env` file (optional):
```
REACT_APP_API_URL=http://localhost:5000/api
```

Default is `http://localhost:5000/api` if not specified.

## Routes

| Route | Access | Purpose |
|---|---|---|
| `/register` | Public | Sign up page |
| `/verify-otp` | Public | OTP verification |
| `/login` | Public | Login page |
| `/dashboard` | Protected | User dashboard |
| `/chat` | Protected | Chat interface |

## How It Works

### Authentication Flow

1. **Register**: User fills name, email, password → OTP sent
2. **Verify OTP**: User enters 6-digit code → Account created
3. **Login**: User enters email/password → JWT token returned
4. **Token Storage**: Token saved to localStorage
5. **Protected Routes**: All requests include `Authorization: Bearer {token}` header
6. **Session Check**: If token expired, user redirected to login

### Chat Flow

1. User types prompt
2. Send button sends to `/api/generate` with Bearer token
3. Backend retrieves RAG context, generates response
4. Response displayed in chat bubble
5. Chat history saved to database

## Styling

Colors (defined in `index.css`):
- Navy: `#0d1b2a` (background)
- Saffron: `#f4a12e` (accent - Dr. Kalam's theme)
- Ivory: `#f5f0e8` (text)
- Error Red: `#e05252`

## Troubleshooting

**"Connection refused at localhost:5000"**
- Make sure backend is running: `python app.py`
- Check backend is listening on port 5000

**"Invalid token" / auto-logout**
- JWT expires after 24 hours (configurable in backend)
- Login again to get new token

**OTP not received**
- Check email spam folder
- Backend may not have email service configured yet

**Styles not loading**
- Clear browser cache (Ctrl+Shift+Delete)
- Restart dev server: `npm start`

## Next Steps

- Deploy to Render.com
- Configure custom domain
- Enable HTTPS
- Set up error logging
- Add analytics

## Support

For issues, check backend logs and browser console (F12).

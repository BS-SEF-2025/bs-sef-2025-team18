# PeerEval Pro - Peer Review System

## Backend Setup and Running

### Prerequisites
- Python 3.8 or higher
- Windows PowerShell

### Setup Steps (PowerShell)

1. **Navigate to project root:**
   ```powershell
   cd C:\Users\ibrah\bs-sef-2025-team18
   ```

2. **Create virtual environment:**
   ```powershell
   python -m venv venv
   ```

3. **Activate virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   If you get an execution policy error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
   Then try activating again.

4. **Install dependencies:**
   ```powershell
   cd backend
   pip install -r requirements.txt
   ```

5. **Run the FastAPI server (from backend folder):**
   ```powershell
   python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```
   
   **Note:** Run this command from the `backend` folder (where `main.py` is located).
   
   The `--reload` flag enables auto-reload on code changes (optional but recommended for development).

### Verify Backend is Running

1. **Check API documentation:**
   Open your browser and navigate to: http://127.0.0.1:8000/docs
   
   You should see the FastAPI interactive documentation (Swagger UI).

2. **Test login endpoint:**
   - In the `/docs` page, expand `POST /auth/login`
   - Click "Try it out"
   - Use test credentials (see below)
   - Click "Execute"
   - Should return: `{"access_token": "...", "role": "student"}`

### Test Credentials

The backend seeds default users on startup:

- **Student:**
  - Username: `student1`
  - Password: `Student123`

- **Instructor:**
  - Username: `instructor1`
  - Password: `Instructor123`

### API Endpoints

- **POST /auth/login** - Login endpoint
  - Request: `{"username": "...", "password": "..."}`
  - Response: `{"access_token": "<token>", "role": "<role>"}`

- **GET /docs** - API documentation (Swagger UI)
- **GET /redoc** - Alternative API documentation (ReDoc)

### Troubleshooting

**Port already in use:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000
# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

**Module not found errors:**
- Ensure you're in the project root directory
- Ensure virtual environment is activated
- Reinstall requirements: `pip install -r backend/requirements.txt`

**CORS errors:**
- Backend is configured to allow all origins (`allow_origins=["*"]`)
- Ensure backend is running on `127.0.0.1:8000`
- Check browser console for specific error messages

## Frontend Setup and Running

### Prerequisites
- Backend must be running on `http://127.0.0.1:8000`
- Modern web browser (Chrome, Firefox, Edge, Safari)

### Running the Frontend

You have two options to run the frontend:

#### Option 1: Simple HTTP Server (Recommended)

1. **Navigate to frontend folder:**
   ```powershell
   cd frontend
   ```

2. **Start a simple HTTP server:**
   ```powershell
   python -m http.server 5500
   ```

3. **Open in browser:**
   - Navigate to: http://localhost:5500
   - Or open: http://localhost:5500/login.html directly

#### Option 2: Direct File Access

1. **Open files directly:**
   - Navigate to the `frontend` folder in your file explorer
   - Double-click `login.html` or `index.html` to open in your browser
   - Note: Some browsers may have CORS restrictions with file:// protocol

### Frontend Structure

- `index.html` - Entry point (redirects to login or dashboard)
- `login.html` - Login page
- `signup.html` - User registration page
- `dashboard.html` - Main dashboard with peer review form
- `protected.js` - Authentication and page protection logic
- `team.js` - Team members loading and display
- `rating.js` - Peer review rating inputs and submission
- `styles.css` - Modern, responsive styling

### Frontend Features

- **Authentication:**
  - Login with username/password
  - Sign up for new accounts
  - Automatic redirect to login if not authenticated
  - Token-based authentication stored in localStorage

- **Dashboard:**
  - Display team members
  - Select teammate to review
  - Rate teammates on multiple criteria (dynamically loaded from backend)
  - Add optional comments (max 500 characters)
  - Submit peer reviews with validation

- **Design:**
  - Modern, clean, professional UI
  - Responsive design (works on mobile and desktop)
  - Gradient background with card-based layout
  - Clear error and success messages

### Frontend Configuration

The backend URL is configured globally in each HTML file:
```javascript
window.BACKEND_URL = "http://127.0.0.1:8000";
```

All scripts use this global variable to avoid hardcoding URLs.

### Troubleshooting Frontend

**CORS errors:**
- Ensure backend is running on `127.0.0.1:8000`
- Use HTTP server (Option 1) instead of file:// protocol
- Check browser console for specific error messages

**Login not working:**
- Verify backend is running: http://127.0.0.1:8000/docs
- Check browser console for network errors
- Ensure credentials are correct (see Test Credentials above)

**Team members not loading:**
- Ensure you're logged in as a student (instructors may not see teammates)
- Check browser console for API errors
- Verify `/peer-reviews/form` endpoint is accessible

**Ratings not submitting:**
- Ensure all required criteria have ratings selected
- Check that a teammate is selected
- Review browser console for validation errors

### Development Notes

- Database file: `backend/app.db` (SQLite)
- Backend auto-seeds users and criteria on startup
- Server binds to `127.0.0.1:8000` (localhost only, not accessible from network)
- Frontend uses localStorage for authentication tokens
- All API calls include `Authorization: Bearer <token>` header

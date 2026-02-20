# Five New Features - Quick Reference Guide

## Feature Overview

### 1. Employee Directory
**Location**: `/directory`
**Access**: Manager and HR Admin roles
**Features**: Grid/List/Org Chart views, real-time search
**API**: GET `/api/v2/employees`
**Files**: 
- Template: `frontend/templates/directory.html`
- Logic: `frontend/static/js/directory.js`

### 2. Calendar Picker for Leave
**Location**: `/leave`
**Access**: All roles
**Features**: Pure CSS/JS calendar, date range selection, weekend disable toggle
**Files**:
- Component: `frontend/static/js/calendar.js`
- Template: `frontend/templates/leave.html`
- Logic: `frontend/static/js/leave.js`

### 3. Chat History Persistence
**Location**: `/chat`
**Access**: All roles
**Features**: LocalStorage + Server persistence, session tracking, auto-save
**API**: 
- GET `/api/v2/chat/history`
- POST `/api/v2/chat/history`
**Files**:
- Logic: `frontend/static/js/chat_v2.js` (enhanced)
- Backend: `src/platform_services/api_gateway.py` (endpoints added)

### 4. Email Notifications (SMTP)
**Access**: Background service
**Features**: HTML emails, graceful fallback, leave/approval templates
**Service**: `src/services/email_service.py`
**Config**: `config/settings.py` (SMTP variables)
**Usage**:
```python
from src.services.email_service import get_email_service
email = get_email_service()
if email.is_configured():
    email.send_leave_notification(...)
```

### 5. File Upload for Documents
**Location**: `/documents`
**Access**: HR Admin and above
**Features**: Drag-drop, progress bar, validation, file grid
**API**: POST `/api/v2/documents/upload`
**Files**:
- Template: `frontend/templates/documents.html` (enhanced)
- Logic: `frontend/static/js/documents.js` (enhanced)

---

## Key Implementation Details

### Directory
- **Grid View**: 280px cards with initials avatars
- **List View**: Table format with email links
- **Org Chart**: Department-based hierarchy
- **Search**: Real-time filtering on name/dept/role/email

### Calendar
- **DateRangePicker Class**: Pure JavaScript
- **Default**: Disables past dates
- **Optional**: Weekend disable toggle
- **Output**: ISO format dates synced to form inputs

### Chat History
- **Storage**: localStorage (role-specific keys)
- **Session**: 30-minute gap = new session
- **Auto-save**: Every 10 seconds
- **Button**: "Clear History" in sidebar header

### Email Service
- **SMTP**: Port 587 with TLS by default
- **Fallback**: Logs email if SMTP not configured
- **Templates**: 
  - Leave notifications (approved/rejected)
  - General approval notifications
- **Config Vars**: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL

### File Upload
- **Max Size**: 10MB
- **Formats**: PDF, DOCX, JPG, PNG, GIF
- **Storage**: `/data/documents/`
- **Progress**: Simulated 0-100% with real-time updates
- **Naming**: Timestamp + original filename for uniqueness

---

## API Reference

### Chat History Endpoints

**GET /api/v2/chat/history**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "id": "conv_xxx",
        "title": "Chat Session",
        "created_at": "2026-02-15T...",
        "messages": [
          {"id": 1, "role": "user", "content": "...", "timestamp": "..."},
          {"id": 2, "role": "agent", "content": "...", "timestamp": "..."}
        ]
      }
    ]
  }
}
```

**POST /api/v2/chat/history**
```json
{
  "conversation_id": "conv_xxx",
  "messages": [{"role": "user", "content": "..."}],
  "title": "Chat",
  "created_at": "2026-02-15T..."
}
```

### Document Upload Endpoint

**POST /api/v2/documents/upload**
- **Request**: multipart/form-data with `file` field
- **Response**:
```json
{
  "success": true,
  "data": {
    "filename": "20260215_082301_doc.pdf",
    "original_name": "doc.pdf",
    "size": 102400,
    "uploaded_at": "2026-02-15T...",
    "url": "/api/v2/documents/download/..."
  }
}
```

---

## Configuration Examples

### SMTP Setup (Gmail)
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM_EMAIL=noreply@company.com
```

### Disable Features
```bash
# Leave SMTP_HOST empty to use fallback logging
SMTP_HOST=
```

---

## Frontend Integration Points

### Call From Any Page
```javascript
// Toast notifications
showToast('Message', 'success|error|info')

// API calls
const response = await apiCall('/api/v2/endpoint', {
    method: 'POST',
    body: JSON.stringify(data)
})

// Role checks
const role = localStorage.getItem('hr_current_role')
```

### Directory Integration
```javascript
// In another page, load and display employees
const response = await apiCall('/api/v2/employees')
const employees = response.data.employees
```

---

## Database Models (Optional)

### Chat Tables
```sql
CREATE TABLE chat_conversations (
    id VARCHAR(100) PRIMARY KEY,
    employee_id INTEGER,
    title VARCHAR(255),
    created_at TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    conversation_id VARCHAR(100),
    role VARCHAR(20),
    content TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id)
);
```

---

## Testing Quick Commands

### Test Directory
```bash
# Visit http://localhost:5050/directory
# Try search, toggle views, copy email
```

### Test Calendar
```bash
# Visit http://localhost:5050/leave
# Click dates, toggle weekends, check form sync
```

### Test Chat History
```bash
# Visit http://localhost:5050/chat
# Send messages, check localStorage
# Refresh page - messages should persist
# Click clear history
```

### Test Email Service
```python
from src.services.email_service import get_email_service
service = get_email_service()
print(service.is_configured())  # False if SMTP not set
service.send_email('test@example.com', 'Subject', '<p>HTML</p>')
```

### Test Document Upload
```bash
# Visit http://localhost:5050/documents
# Drag file or click browse
# Monitor /data/documents/ for file
```

---

## Troubleshooting

### Directory shows no employees
- Check that `/api/v2/employees` endpoint returns data
- Verify user has manager or hr_admin role
- Check browser console for API errors

### Calendar not syncing with date inputs
- Ensure calendar.js is loaded before leave.js
- Check initializeCalendarPicker() is called in DOMContentLoaded
- Check form inputs have correct IDs: start-date, end-date

### Chat history not persisting
- Check browser localStorage (console: localStorage.getItem('hr_conversations_...'))
- Verify server endpoints if using server sync
- Check X-User-Role header is being sent

### Emails not sending
- Check SMTP_HOST env var is set
- Verify credentials are correct
- Check logs for SMTP errors
- Fallback mode logs emails to console if SMTP fails

### File upload fails
- Check file size is under 10MB
- Verify format is PDF, DOCX, JPG, PNG, or GIF
- Check /data/documents/ directory exists and is writable
- Verify /api/v2/documents/upload endpoint is accessible

---

## Code Snippets for Integration

### In Leave Approval Workflow
```python
# After approving leave in _approve_request()
from src.services.email_service import get_email_service

service = get_email_service()
if service.is_configured():
    service.send_leave_notification(
        to_email=employee.email,
        employee_name=f"{employee.first_name} {employee.last_name}",
        leave_type=leave.leave_type,
        start_date=leave.start_date.isoformat(),
        end_date=leave.end_date.isoformat(),
        status="approved"
    )
```

### In Chat Initialization
```javascript
// Already implemented in chat_v2.js
// Automatically called on page load:
initChatServerSync()
```

### In Document Operations
```javascript
// Upload file
const formData = new FormData()
formData.append('file', fileInput.files[0])
const response = await apiCall('/api/v2/documents/upload', {
    method: 'POST',
    body: formData
})

// Download file
window.open(`/api/v2/documents/download/${filename}`)
```


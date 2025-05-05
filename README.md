# tweetup
A repository for the TweetUp app.

# TweetUp Application Architecture

## Overview
TweetUp is a desktop application that allows users to save and organize tweets into "Tweetbooks" and displays them at scheduled intervals.

## Technology Stack
- **Backend**: Python
  - Flask for the API server
  - SQLite for data storage
  - APScheduler for scheduling notifications
- **Frontend**: JavaScript
  - React for UI components
  - Electron for desktop application packaging

## Component Structure

### Python Backend Components
1. **Database Manager**
   - Handles all interactions with SQLite database
   - Manages tweet storage, organization, and retrieval

2. **Notification Service**
   - Schedules when tweets should be displayed
   - Handles timing logic (random intervals, specific times)

3. **API Server**
   - Provides endpoints for the frontend to interact with
   - Routes for adding, removing, and organizing tweets

### JavaScript Frontend Components
1. **Main Application UI**
   - Tweet browsing and management interface
   - Tweetbook organization system

2. **Settings Panel**
   - Configuration for notification frequency, timing
   - Active Tweetbook selection

3. **Notification Component**
   - Displays tweets as desktop notifications
   - Handles user interaction with notifications

## Data Flow
1. User saves tweets through the UI
2. Frontend sends tweet data to Python backend API
3. Backend stores tweets in SQLite database
4. Notification Service checks schedule and database
5. At scheduled times, backend triggers frontend to display notifications
6. Frontend renders the tweet notification to user

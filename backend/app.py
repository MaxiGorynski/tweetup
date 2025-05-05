#!/usr/bin/env python3
# backend/app.py - Main Flask application for TweetUp backend

import os
import json
import sqlite3
import datetime
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import random

app = Flask(__name__)

# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), 'tweetup.db')


def init_db():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tweetbooks table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tweetbooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create tweets table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tweets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tweet_id TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        author TEXT NOT NULL,
        tweetbook_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_shown TIMESTAMP,
        FOREIGN KEY (tweetbook_id) REFERENCES tweetbooks(id)
    )
    ''')

    # Create settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        notification_frequency TEXT DEFAULT 'hourly',
        active_tweetbook_id INTEGER,
        start_time TEXT DEFAULT '09:00',
        end_time TEXT DEFAULT '17:00',
        random_mode BOOLEAN DEFAULT 1,
        FOREIGN KEY (active_tweetbook_id) REFERENCES tweetbooks(id)
    )
    ''')

    # Insert default tweetbook if it doesn't exist
    cursor.execute(
        "INSERT OR IGNORE INTO tweetbooks (id, name, description) VALUES (1, 'Default', 'Your default collection of tweets')")

    # Insert default settings if they don't exist
    cursor.execute("INSERT OR IGNORE INTO settings (id, active_tweetbook_id) VALUES (1, 1)")

    conn.commit()
    conn.close()


# Initialize database
init_db()

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.start()


def get_random_tweet(tweetbook_id=None):
    """Get a random tweet from the specified tweetbook"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if tweetbook_id:
        cursor.execute(
            "SELECT id, tweet_id, content, author FROM tweets WHERE tweetbook_id = ? ORDER BY RANDOM() LIMIT 1",
            (tweetbook_id,)
        )
    else:
        cursor.execute("SELECT id, tweet_id, content, author FROM tweets ORDER BY RANDOM() LIMIT 1")

    tweet = cursor.fetchone()

    if tweet:
        tweet_id, tweet_original_id, content, author = tweet

        # Update last_shown timestamp
        cursor.execute(
            "UPDATE tweets SET last_shown = CURRENT_TIMESTAMP WHERE id = ?",
            (tweet_id,)
        )
        conn.commit()

        return {
            "id": tweet_id,
            "tweet_id": tweet_original_id,
            "content": content,
            "author": author
        }

    conn.close()
    return None


def show_tweet_notification():
    """Retrieve a tweet and send notification to the frontend"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get active tweetbook from settings
    cursor.execute("SELECT active_tweetbook_id FROM settings WHERE id = 1")
    result = cursor.fetchone()

    if result:
        active_tweetbook_id = result[0]
        tweet = get_random_tweet(active_tweetbook_id)

        if tweet:
            # In a real application, this would communicate with the frontend
            # For now, we'll just print to console
            print(f"NOTIFICATION: Tweet by {tweet['author']}: {tweet['content']}")

            # In production, this would use a websocket or similar to push to frontend
            return tweet

    conn.close()
    return None


def update_scheduler():
    """Update the scheduler based on current settings"""
    # Remove all existing jobs
    scheduler.remove_all_jobs()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT notification_frequency, start_time, end_time, random_mode FROM settings WHERE id = 1")
    result = cursor.fetchone()

    if result:
        frequency, start_time, end_time, random_mode = result

        if random_mode:
            # Random mode - schedule at variable intervals within the time window
            if frequency == 'hourly':
                interval_minutes = random.randint(30, 90)
            elif frequency == 'daily':
                interval_minutes = random.randint(720, 1440)  # 12-24 hours
            else:  # Use 'custom' as fallback
                interval_minutes = random.randint(15, 180)  # 15min-3hours

            scheduler.add_job(
                show_tweet_notification,
                IntervalTrigger(minutes=interval_minutes),
                id='show_tweet'
            )
        else:
            # Scheduled mode - use specific times
            if frequency == 'hourly':
                scheduler.add_job(
                    show_tweet_notification,
                    CronTrigger(hour='9-17', minute='0'),
                    id='show_tweet'
                )
            elif frequency == 'daily':
                # Parse the start_time (format: "HH:MM")
                hour, minute = start_time.split(':')
                scheduler.add_job(
                    show_tweet_notification,
                    CronTrigger(hour=hour, minute=minute),
                    id='show_tweet'
                )
            elif frequency == 'custom':
                # Custom schedules would be implemented here
                pass

    conn.close()


# Update scheduler with default settings
update_scheduler()


# API Routes
@app.route('/api/tweetbooks', methods=['GET'])
def get_tweetbooks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, description FROM tweetbooks")
    tweetbooks = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(tweetbooks)


@app.route('/api/tweetbooks', methods=['POST'])
def create_tweetbook():
    data = request.json
    name = data.get('name')
    description = data.get('description', '')

    if not name:
        return jsonify({"error": "Tweetbook name is required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO tweetbooks (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        tweetbook_id = cursor.lastrowid

        conn.close()
        return jsonify({"id": tweetbook_id, "name": name, "description": description}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "A tweetbook with this name already exists"}), 400


@app.route('/api/tweets', methods=['POST'])
def save_tweet():
    data = request.json
    tweet_id = data.get('tweet_id')
    content = data.get('content')
    author = data.get('author')
    tweetbook_id = data.get('tweetbook_id', 1)  # Default tweetbook if not specified

    if not all([tweet_id, content, author]):
        return jsonify({"error": "Tweet ID, content, and author are required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO tweets (tweet_id, content, author, tweetbook_id) VALUES (?, ?, ?, ?)",
            (tweet_id, content, author, tweetbook_id)
        )
        conn.commit()
        tweet_db_id = cursor.lastrowid

        conn.close()
        return jsonify({
            "id": tweet_db_id,
            "tweet_id": tweet_id,
            "content": content,
            "author": author,
            "tweetbook_id": tweetbook_id
        }), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "This tweet has already been saved"}), 400


@app.route('/api/tweets/tweetbook/<int:tweetbook_id>', methods=['GET'])
def get_tweets_by_tweetbook(tweetbook_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT t.id, t.tweet_id, t.content, t.author, t.created_at, t.last_shown
        FROM tweets t
        WHERE t.tweetbook_id = ?
        ORDER BY t.created_at DESC
        """,
        (tweetbook_id,)
    )

    tweets = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(tweets)


@app.route('/api/settings', methods=['GET'])
def get_settings():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.notification_frequency, s.start_time, s.end_time, s.random_mode,
               s.active_tweetbook_id, t.name as active_tweetbook_name
        FROM settings s
        JOIN tweetbooks t ON s.active_tweetbook_id = t.id
        WHERE s.id = 1
    """)

    settings = dict(cursor.fetchone())
    conn.close()

    return jsonify(settings)


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.json
    frequency = data.get('notification_frequency')
    active_tweetbook_id = data.get('active_tweetbook_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    random_mode = data.get('random_mode')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    update_fields = []
    update_values = []

    if frequency:
        update_fields.append("notification_frequency = ?")
        update_values.append(frequency)

    if active_tweetbook_id:
        update_fields.append("active_tweetbook_id = ?")
        update_values.append(active_tweetbook_id)

    if start_time:
        update_fields.append("start_time = ?")
        update_values.append(start_time)

    if end_time:
        update_fields.append("end_time = ?")
        update_values.append(end_time)

    if random_mode is not None:
        update_fields.append("random_mode = ?")
        update_values.append(1 if random_mode else 0)

    if update_fields:
        query = f"UPDATE settings SET {', '.join(update_fields)} WHERE id = 1"
        cursor.execute(query, update_values)
        conn.commit()

        # Update the scheduler with new settings
        update_scheduler()

    conn.close()
    return jsonify({"message": "Settings updated successfully"})


@app.route('/api/tweets/random', methods=['GET'])
def get_random_tweet_endpoint():
    tweetbook_id = request.args.get('tweetbook_id')

    if tweetbook_id:
        try:
            tweetbook_id = int(tweetbook_id)
        except ValueError:
            return jsonify({"error": "Invalid tweetbook ID"}), 400

    tweet = get_random_tweet(tweetbook_id)

    if tweet:
        return jsonify(tweet)
    else:
        return jsonify({"error": "No tweets found"}), 404


@app.route('/api/tweets/<int:tweet_id>', methods=['DELETE'])
def delete_tweet(tweet_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tweets WHERE id = ?", (tweet_id,))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return jsonify({"message": "Tweet deleted successfully"})
    else:
        conn.close()
        return jsonify({"error": "Tweet not found"}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
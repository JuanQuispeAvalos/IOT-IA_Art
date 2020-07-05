DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS artist;
DROP TABLE IF EXISTS genre;
DROP TABLE IF EXISTS iota;
DROP TABLE IF EXISTS job;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  iota_address TEXT NOT NULL
);

CREATE TABLE artist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ai_name TEXT NOT NULL,
  code TEXT NOT NULL,
  surcharge INTEGER NOT NULL DEFAULT 0,
  genre_id TEXT NOT NULL,
  average_time INTEGER,
  FOREIGN KEY (author_id) REFERENCES user (id),
  FOREIGN KEY (genre_id) REFERENCES genre (id)
);

CREATE TABLE genre (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  genre_name TEXT NOT NULL
);

CREATE TABLE iota (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seed TEXT NOT NULL,
  addr_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE job (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  access_key TEXT UNIQUE NOT NULL,
  addr_index INTEGER NOT NULL,
  ai_id INTEGER NOT NULL,
  completed TIMESTAMP,
  filename TEXT,
  FOREIGN KEY (ai_id) REFERENCES artist (id)
);

INSERT INTO genre (genre_name)
VALUES
    ('abstract'),
    ('cities'),
    ('landscapes'),
    ('portraits'),
    ('still-life');
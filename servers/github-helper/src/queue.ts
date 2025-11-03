import { open, Database } from 'sqlite';
import sqlite3 from 'sqlite3';
import path from 'path';

let db: Database;

const DB_FILE = path.join(process.cwd(), 'git-helper-queue.db');

/**
 * Initializes the database and creates the 'jobs' table if it doesn't exist.
 */
export async function initQueueDb(): Promise<Database> {
  if (db) return db;

  db = await open({
    filename: DB_FILE,
    driver: sqlite3.Database,
  });

  // This is "Write-Ahead Logging" mode. It's much faster for
  // concurrent reading and writing, which is exactly what we're doing.
  await db.exec('PRAGMA journal_mode = WAL;');
  
  await db.exec(`
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      params TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'queued',
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      processedAt DATETIME,
      error TEXT
    );
  `);
  
  console.error(`[Queue] Database initialized at ${DB_FILE}`);
  return db;
}

/**
 * Adds a new job to the queue.
 * This is called by your MCP server (index.ts).
 */
export async function addJobToQueue(id: string, params: object): Promise<void> {
  const db = await initQueueDb();
  await db.run(
    'INSERT INTO jobs (id, params) VALUES (?, ?)',
    id,
    JSON.stringify(params) // Store params as a JSON string
  );
}

/**
 * Gets the next available job and marks it as 'running'.
 * This is a transactional "dequeue" operation, safe for multiple workers.
 * This is called by your worker (worker.ts).
 */
export async function getNextJob(): Promise<{ id: string, params: any } | null> {
  const db = await initQueueDb();

  // We use a transaction to make this "atomic" (safe)
  try {
    await db.exec('BEGIN IMMEDIATE TRANSACTION');

    // Find the oldest queued job
    const job = await db.get(`
      SELECT id, params FROM jobs 
      WHERE status = 'queued' 
      ORDER BY createdAt 
      LIMIT 1
    `); // Adding "FOR UPDATE" is common in other SQLs, but this is fine in WAL mode

    if (!job) {
      await db.exec('COMMIT');
      return null;
    }

    // Mark it as running so no other worker picks it up
    await db.run(
      "UPDATE jobs SET status = 'running', processedAt = CURRENT_TIMESTAMP WHERE id = ?",
      job.id
    );

    await db.exec('COMMIT');
    
    return {
      id: job.id,
      params: JSON.parse(job.params)
    };
  } catch (e: any) {
    await db.exec('ROLLBACK');
    console.error('[Queue] Error getting next job:', e.message);
    return null;
  }
}

/**
 * Marks a job as completed successfully.
 */
export async function completeJob(id: string): Promise<void> {
  const db = await initQueueDb();
  await db.run(
    "UPDATE jobs SET status = 'completed' WHERE id = ?",
    id
  );
}

/**
 * Marks a job as failed and stores the error message.
 */
export async function failJob(id: string, error: string): Promise<void> {
  const db = await initQueueDb();
  await db.run(
    "UPDATE jobs SET status = 'failed', error = ? WHERE id = ?",
    id,
    error
  );
}
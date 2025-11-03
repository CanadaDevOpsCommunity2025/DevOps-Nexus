/*
 * MCP-for-Beginners: 03-GettingStarted/05-stdio-server
 *
 * This is the main file for your 'GIT and GITHUB Helper' MCP server.
 * It listens for JSON-RPC requests on 'stdin', queues the requested task,
 * and writes JSON-RPC responses to 'stdout'.
 */

import * as readline from 'readline';
import { randomUUID } from 'crypto';

// --- MCP Request/Response Types ---

interface McpRequest {
  jsonrpc: '2.0';
  id: number | string;
  method: string;
  params: unknown;
}

interface McpResponse {
  jsonrpc: '2.0';
  id: number | string;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

// --- Our Task-Specific Types ---

interface CherryPickParams {
  repository: string;
  targetBranch: string;
  prFilterQuery: string;
  callbackUrl?: string; // Optional: where to send a webhook on completion
}

interface JobStatus {
  jobId: string;
  status: 'queued' | 'failed' | 'running';
  message: string;
}

// --- Job Queue Stub ---

/**
 * In a real application, this function would connect to a message broker
 * like Redis (e.g., using BullMQ) or RabbitMQ to enqueue the job.
 *
 * The actual cherry-pick script would be run by a separate "Worker"
 * process listening to that queue.
 */
async function enqueueCherryPickJob(params: CherryPickParams): Promise<JobStatus> {
  // Use console.error for logging, so it goes to stderr and doesn't
  // interfere with the stdout JSON-RPC response.
  console.error(
    `[INFO] Enqueuing job for repo: ${params.repository}`
  );
  
  // 1. Validate parameters (example)
  if (!params.repository || !params.targetBranch || !params.prFilterQuery) {
    throw new Error('Missing required parameters: repository, targetBranch, prFilterQuery');
  }

  // 2. Add to queue (simulated)
  const jobId = randomUUID();
  // Example: await myJobQueue.add('cherry-pick-task', { ...params, jobId });
  
  console.error(`[INFO] Job enqueued with ID: ${jobId}`);

  // 3. Return the immediate "accepted" status
  return {
    jobId: jobId,
    status: 'queued',
    message: 'Cherry-pick job has been queued successfully.',
  };
}

// --- Helper to write JSON-RPC responses to stdout ---
function writeResponse(response: McpResponse) {
  // Use console.log ONLY for the final JSON-RPC response
  console.log(JSON.stringify(response));
}

// --- Main Server Function ---

async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false, // We are not in a TTY
  });

  console.error(
    '[INFO] GIT/GITHUB Helper MCP server started. Listening on stdin...'
  );

  rl.on('line', async (line) => {
    let request: McpRequest;

    // 1. Parse the incoming request
    try {
      request = JSON.parse(line) as McpRequest;
    } catch (e) {
      console.error(`[ERROR] Failed to parse input JSON: ${line}`);
      // Cannot send a valid response if we can't parse the request/ID
      return;
    }

    // 2. Process the request
    try {
      switch (request.method) {
        
        // This is our main operation
        case 'tasks/cherryPickFromPrFilter':
          const jobStatus = await enqueueCherryPickJob(
            request.params as CherryPickParams
          );
          writeResponse({
            jsonrpc: '2.0',
            id: request.id,
            result: jobStatus,
          });
          break;

        // A standard health-check operation
        case 'health/ping':
          writeResponse({
            jsonrpc: '2.0',
            id: request.id,
            result: { status: 'ok', service: 'git-helper' },
          });
          break;

        default:
          throw new Error(`Unknown method: ${request.method}`);
      }
    } catch (error: any) {
      // 3. Handle any errors during processing
      console.error(
        `[ERROR] Failed to process request ${request.id}: ${error.message}`
      );
      writeResponse({
        jsonrpc: '2.0',
        id: request.id,
        error: {
          code: -32000, // MCP/JSON-RPC internal error code
          message: error.message || 'An unknown server error occurred.',
        },
      });
    }
  });
}

// Start the server
main().catch((e) => {
  console.error(`[FATAL] Server crashed: ${e.message}`);
  process.exit(1);
});
/*
 * This is the main file for your 'GIT and GITHUB Helper' MCP server.
 * It uses the '@modelcontextprotocol/sdk/server' to handle all
 * stdio communication and JSON-RPC method routing.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { randomUUID } from 'crypto';
import { z } from "zod";
import { initQueueDb, addJobToQueue } from './queue.js'; // <-- Import our queue

// --- Our Task-Specific Types ---
type CherryPickParamsType = {
  repository: string;
  targetBranch: string;
  prFilterQuery: string;
  callbackUrl?: string;
};

type JobStatusType = {
  jobId: string;
  status: 'queued' | 'failed' | 'running';
  message: string;
};

const CherryPickParams = z.object({
  repository: z.string().describe("Repository name"),
  targetBranch: z.string().describe("Target branch for cherry-pick"),
  prFilterQuery: z.string().describe("Pull request filter query"),
  callbackUrl: z.string().url().optional().describe("Optional callback URL"),
});

const JobStatus = z.object({
  jobId: z.string(),
  status: z.enum(['queued', 'failed', 'running']),
  message: z.string(),
});

const server = new Server(
  {
    name: "github-helper-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "cherry-pick",
        description: "Cherry-pick commits from PRs based on a filter query to a target branch",
        inputSchema: {
          type: "object",
          properties: {
            repository: { type: "string", description: "Repository name" },
            targetBranch: { type: "string", description: "Target branch for cherry-pick" },
            prFilterQuery: { type: "string", description: "Pull request filter query" },
            callbackUrl: { type: "string", description: "Optional callback URL" },
          },
          required: ["repository", "targetBranch", "prFilterQuery"],
        },
      },
      {
        name: "health",
        description: "Health check tool",
        inputSchema: {
          type: "object",
          properties: {
          },
        },
      },
      {
        name: "get_server_info",
        description: "Get information about this MCP server",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "cherry-pick": {
      const { repository, targetBranch, prFilterQuery, callbackUrl } = CherryPickParams.parse(args);
      const result = await enqueueCherryPickJob({ repository, targetBranch, prFilterQuery, callbackUrl });
      console.error(`Enqueued cherry-pick job: ${JSON.stringify(result)}`); // Log to stderr
      return {
        content: [
          {
            type: "text",
            text: `Cherry-pick job enqueued with ID: ${result.jobId}`,
          },
        ],
      };
    }

    case "get_server_info": {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              server_name: "github-helper-server",
              version: "1.0.0",
              transport: "stdio",
              capabilities: ["tools"],
              description: "GitHub Helper MCP server using stdio transport (MCP 2025-06-18 specification)",
            }, null, 2),
          },
        ],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});
// --- Job Queue Stub ---

/**
 * In a real application, this function would connect to a message broker
 * like Redis (e.g., using BullMQ) or RabbitMQ to enqueue the job.
 */
async function enqueueCherryPickJob(params: CherryPickParamsType): Promise<JobStatusType> {
  // Use server-side logging. This will go to stderr.
  console.error(
    `[INFO] Enqueuing job for repo: ${params.repository}`
  );
  
  // 1. Validate parameters (example)
  if (!params.repository || !params.targetBranch || !params.prFilterQuery) {
    // The SDK will catch this error and format it as a JSON-RPC error
    throw new Error('Missing required parameters: repository, targetBranch, prFilterQuery');
  }

  // 2. Add to queue (simulated)
  const jobId = randomUUID();
  await addJobToQueue(jobId, params);

  console.error(`[INFO] Job enqueued with ID: ${jobId}`);

  // 3. Return the result. The SDK will format this as a JSON-RPC response.
  return {
    jobId: jobId,
    status: 'queued',
    message: 'Cherry-pick job has been queued successfully.',
  };
}

// --- Main Server Function ---
// Start the server using stdio transport
async function runServer() {
  console.error("Starting MCP stdio server..."); // Log to stderr
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Server connected via stdio transport"); // Log to stderr
  await initQueueDb();
}

// Handle process termination gracefully
process.on("SIGINT", () => {
  console.error("Received SIGINT, shutting down gracefully");
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.error("Received SIGTERM, shutting down gracefully");
  process.exit(0);
});

// Start the server
runServer().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
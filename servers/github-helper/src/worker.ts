import { execSync } from 'child_process';
import { 
  getNextJob, 
  completeJob, 
  failJob 
} from './queue';
import path from 'path';
import axios from 'axios';

// --- Configuration ---
// Path to where the worker should check out the code
const WORKSPACE_DIR = '/opt/mcp/workspaces'; 

// How long to wait (in ms) before checking for a new job
const POLL_INTERVAL = 5000; // 5 seconds

// Helper to run shell commands
function run(command: string) {
  console.log(`[Worker] > ${command}`);
  execSync(command, { encoding: 'utf8', stdio: 'inherit' });
}

/**
 * The main logic for processing a single cherry-pick job.
 */
async function processJob(jobId: string, params: { repository: string, targetBranch: string, prFilterQuery: string }): Promise<void> {
  const { repository, targetBranch, prFilterQuery } = params;
  const WORKSPACE = path.join(WORKSPACE_DIR, repository);

  console.log(`[Worker] Processing job ${jobId} for ${repository}`);
  
  // --- 1. Get PR Data ---
  console.log('[Worker] Fetching PRs...');
  const prDataJson = execSync(
    `gh pr list --repo "${repository}" --search "${prFilterQuery}" --state merged --sort merged-at --order asc --json mergedAt,number,mergeCommit --limit 9999`
  ).toString();

  const all_prs = JSON.parse(prDataJson) as {
    mergedAt: string;
    number: number;
    mergeCommit: { oid: string };
  }[];

  if (!all_prs.length) {
    console.log('[Worker] No matching PRs found. Job complete.');
    return; // This is a success, not an error
  }

  const commitsToPick = all_prs.map(pr => pr.mergeCommit.oid);

  // --- 2. Prepare Local Repo ---
  console.log(`[Worker] Setting up workspace in ${WORKSPACE}...`);
  if (!require('fs').existsSync(WORKSPACE)) {
    run(`git clone --branch ${targetBranch} --single-branch https://github.com/${repository}.git "${WORKSPACE}"`);
  }
  process.chdir(WORKSPACE); // Change directory
  run(`git fetch --all`);
  run(`git checkout ${targetBranch}`);
  run(`git reset --hard origin/${targetBranch}`);
  run(`git pull origin ${targetBranch}`);

  // --- 3. Execute Cherry-Picks ---
  console.log(`[Worker] Found ${commitsToPick.length} commits to pick...`);
  for (const sha of commitsToPick) {
    try {
      execSync(`git branch --contains ${sha} | grep ${targetBranch}`);
      console.log(`[Worker] Commit ${sha} is already on ${targetBranch}. Skipping.`);
      continue;
    } catch (e) {
      // Commit is not on the branch, proceed
    }

    console.log(`[Worker] Picking commit: ${sha}`);
    run(`git cherry-pick ${sha}`); // This will throw on conflict
  }

  // --- 4. Push Changes ---
  console.log('[Worker] All commits cherry-picked. Pushing changes...');
  run(`git push origin ${targetBranch}`);
  
  console.log(`[Worker] Job ${jobId} completed successfully.`);
}

/**
 * Sends a webhook notification to the callbackUrl (if provided).
 * This is "fire and forget" - we don't wait for the client's response.
 */
function sendWebhook(params: any, status: 'completed' | 'failed', error?: string) {
  const { callbackUrl } = params;

  if (!callbackUrl) {
    // No callback URL provided, nothing to do
    return; 
  }

  const payload = {
    jobId: params.jobId, // We need to pass the jobId to the processJob function
    status: status,
    repository: params.repository,
    error: error || null
  };

  console.log(`[Worker] Sending webhook to: ${callbackUrl}`);
  
  axios.post(callbackUrl, payload)
    .then(response => {
      console.log(`[Worker] Webhook sent successfully.`);
    })
    .catch(err => {
      console.error(`[Worker] Failed to send webhook: ${err.message}`);
    });
}

/**
 * The main worker loop.
 */
async function main() {
  // Ensure 'gh' is authenticated with GH_TOKEN
  if (!process.env.GH_TOKEN) {
    console.error('[FATAL] GH_TOKEN environment variable is not set!');
    process.exit(1);
  }
  // Configure git to use the token (as discussed previously)
  run(`git config --global url."https://${process.env.GH_TOKEN}@github.com/".insteadOf "https://github.com/"`);

  console.log('[Worker] Worker process started. Waiting for jobs...');
  
  while (true) {
    let job = null;
    try {
      job = await getNextJob();
      
      if (job) {
        // We found a job!
        const jobParams = { ...job.params, jobId: job.id }; // <-- Pass the ID
        
        try {
          await processJob(job.id, jobParams);
          await completeJob(job.id);
          
          // --- Send SUCCESS Webhook ---
          sendWebhook(jobParams, 'completed');

        } catch (e: any) {
          // Job failed (e.g., merge conflict)
          console.error(`[Worker] Job ${job.id} failed: ${e.message}`);
          
          if (e.message.includes('cherry-pick')) {
            // ... (abort logic) ...
          }
          await failJob(job.id, e.message);

          // --- Send FAILURE Webhook ---
          sendWebhook(jobParams, 'failed', e.message);
        }
      } else {
        // ... (wait logic) ...
      }
    } catch (e: any) {
      // ... (critical error logic) ...
    }
  }
}

// Start the worker
main().catch((e) => {
  console.error(`[FATAL] Worker crashed: ${e.message}`);
  process.exit(1);
});

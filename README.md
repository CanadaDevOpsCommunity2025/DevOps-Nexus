# DevOps Nexus

## Team
Canada DevOps Community of Practice - Toronto Hackathon Series - Team 12

Project Name - DevOps Nexus

Team Mentor -

Participant Names -

     Team Lead - Jincheng Wang
     Team Members - Fahad, Jianxin, Yihui

## Background
In our product software development, we need to maintain parallel releases, and some code is needed in multiple release branches. The internal process requires all code changes to be integrated in a on-going development branch, which is master, and then go through the CI/CD pipeline for testing. Eventually when the test is done, the code is cherry picked into the target release branches, and continue the next round of testing before release. The challenge here is the code repo maintainer has to keep track of the changes and cherry pick them to the target release branches after the testing. It is not always easy to remember.

In general, the development team is using GenAI to assist coding, so the copilot in vscode is commonly used. Some developers also use cursor and claude code. It would be a great idea if we can add some capabilities let our agent understand our cherry-pick task and invoke it from our prompt.

After some learning and research, MCP server is the idea solution as it can provide the function and can be consumed by any type of agents.

## Goal

### Git-Helper MCP Server
As the solution to our immediate challenge, we would like to create an Git-Helper MCP server to help our code maintainer to do cherry pick easily from their code assistant agent, such as Copilot in vscode.

### Internal MCP Hub and registry
As more developers are interested in contributing the MCP Servers to solve their unique problems, they may also want to share their MCP servers across the team. So, it would be great that we can build a simple internal MCP hub to host those MCP servers, and have an registry to know all available MCP servers and their health status.

### Multi-Agents for complicated tasks
For some complicated tasks, especially involving interacting with multiple systems, we may need more than one agents to complete the work. For example, if we create a jira issue to track the cherry-pick task, we would need the agent to read and understand the jira ticket and describe it to another agent to analyze the github repo to figure out what commits are missing, and then cherry pick them. it would also be great to create such multiple agents to work for us smartly.

## Progress
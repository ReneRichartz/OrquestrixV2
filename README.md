# Orquestrix
Orquestrix will be **the** Microsoft Dynamics 365 Finance and Supply Chain Functional and Technical Solution Architect.
Orquestrix will use different vector stores as knowledge source, best practices, real life and demo examples and separated customer data.
Orquestrix will have a chat interface based on openAI client.responses API using GPT4.5 or GPT 5 model.
Orquestrix will have workers - workers are threads with assistants messages using GPT 4 or GPT 4.1 models with code-interpreter and file-search to interpret and generate CSV Files that can be downloaded
Orquestrix will manage projects that combine chats and workers

Orquestrix has its own logo 

orquestrix_logo.png

using following color scheme

Deep Blue: #1E3A57

Silver Gray: #A7A9AC

White: #FFFFFF

Orquestrix application will be a light design, not dark

# Used Technologies
- Python as development language
- Flask as Framework for Web UI
- SQL database (example Postgres)
- openAI - strictly use python API

# OpenAI Integration
- strictly use latest openAI python api
- api reference documentation can be found on https://platform.openai.com/docs/api-reference/introduction

`from openai import OpenAI`
`client = OpenAI()`

openAI.png

## Response Client (Chat)
- In the application the communication with the response client will be called chat
- every chat will be stored persistent in database
- every chat belongs to a user 
- a chat can be connected to a project
- Response Client will use GPT 4.5 / GPT 5 model only!
- chat will have attached vector
- chat will have attached files
### response object
https://platform.openai.com/docs/api-reference/responses/object
### Orquestrix used object parameters
`"instructions": (chat objective),
  "max_output_tokens": (Number Input),
  "model": (List of models GPT 4.5 or higher),
  "parallel_tool_calls": true,
  "reasoning": {
    "effort": (minimal, low, medium, and high),
    "summary": (auto, concise, or detailed)
  },
  "text": {
    "format": {
      "type": "text"
    }
  },
  "tool_choice": "auto",
  "tools": [(Code-Interpreter, File-Search)], `
### create response
response = client.responses.create
### retrieve response
response = client.responses.retrieve
### delete response
**DO NOT IMPLEMENT IN VERSION 1**
response = client.responses.delete
### cancel response
**DO NOT IMPLEMENT IN VERSION 1**
response = client.responses.cancel
### list input items
**DO NOT IMPLEMENT IN VERSION 1** 
response = client.responses.input_items.list
https://platform.openai.com/docs/api-reference/responses/list


## Threads (called Workers)
- In the application the communication with the thread will be worker session
- every worker session will be stored persistent in database
- every worker session belongs to a user 
- a worker session is always connected to a project
- worker sessions will use GPT 4 / GPT 4.1 models!
- threads will have one attached vector
- threads will have multiple attached files
### Thread Object
https://platform.openai.com/docs/api-reference/threads/object
### Orquestrix used object parameters
**Parameter : tool_resources**
A set of resources that are made available to the assistant's tools in this thread. The resources are specific to the type of tool. For example, the code_interpreter tool requires a list of file IDs, while the file_search tool requires a list of vector store IDs.
https://platform.openai.com/docs/api-reference/threads/object#threads/object-tool_resources

**code_interpreter**
A list of file IDs made available to the code_interpreter tool. There can be a maximum of 20 files associated with the tool.
**file_search**
The vector store attached to this thread. There can be a maximum of 1 vector store attached to the thread.
### create new thread
empty_thread = client.beta.threads.create
### retrieve thread
my_thread = client.beta.threads.retrieve
### update thread
my_updated_thread = client.beta.threads.update
### delete thread
response = client.beta.threads.delete

## Assistants
- Assistants will be used for GPT4 communication
- Code-Interpreter and File-search are essential
- assistants will be stored in openAI
- assitants will be synced with openAI
### Assistants Object 
https://platform.openai.com/docs/api-reference/assistants/object
### Orquestrix used object parameters
` "object": "assistant",
  "name": (Text),
  "description": (Text),
  "model": (List of Models below GPT 4.5),
  "instructions": (Text),
  "tools": [
    {
      "type": "code_interpreter“,
      "type": "file_search“
    }
  ],
  "temperature": (Slider from 0.1 to 1.0),
  "response_format": "Text"`

### create new assistant
my_assistant = client.beta.assistants.create
### List all Assistants
my_assistants = client.beta.assistants.list
### retrieve Assistant
my_assistant = client.beta.assistants.retrieve
### Update Assistant
my_updated_assistant = client.beta.assistants.update
### Delete Assistant
response = client.beta.assistants.delete

## Messages
### Messages Object
https://platform.openai.com/docs/api-reference/messages/object
### Orquestrix used object parameters
`{
  "thread_id": (THREAD ID),
  "role": "assistant",
  "assistant_id": (ASSISTANT ID),
  "attachments": [(openAI Created Files)],`
### create new message
thread_message = client.beta.threads.messages.create
### list all messages 
thread_messages = client.beta.threads.messages.list
### retrieve message
message = client.beta.threads.messages.retrieve
### update message
message = client.beta.threads.messages.update
### delete message
deleted_message = client.beta.threads.messages.delete


## File
- will be used for file upload to file store **only**
- Purpose : assistants
### File Object
https://platform.openai.com/docs/api-reference/files/object
### Orquestrix used object parameters
` "filename": (Filename),
  "purpose": "assistants“,`**Always assistants**
### create file
client.files.create
### retrieve file
client.files.retrieve
### delete file
client.files.delete
### get content of a file
content = client.files.content

## Vector Stores
### Vector store object
https://platform.openai.com/docs/api-reference/vector_stores/object
### Orquestrix used object parameters
` "name": (Name Input)`
### create vector store
vector_store = client.vector_stores.create
### list vector stores
vector_stores = client.vector_stores.list
### retrieve vector store
vector_store = client.vector_stores.retrieve
### update vector store
vector_store = client.vector_stores.update
### delete vector store
deleted_vector_store = client.vector_stores.delete

## Vector Store File
### Vector store files file object
https://platform.openai.com/docs/api-reference/vector_stores_files/file-object
### Orquestrix used object parameters
`“vector_store_id": "vs_abc123",
  "chunking_strategy": {
    "type": "static",
    "static": {
      "max_chunk_size_tokens": 800, **Static**
      "chunk_overlap_tokens": 400 **Static**
    }
  }`
### create file in vector store
vector_store_file = client.vector_stores.files.create
### List files in vector store
vector_store_files = client.vector_stores.files.list
### retrieve vector store file
vector_store_file = client.vector_stores.files.retrieve
### delete vector store file
deleted_vector_store_file = client.vector_stores.files.delete


# UI
## Application Header Menue
1. Create Chat Button with
	2. + to create chat with standard role
	3. Dropdown select role and create chat with selected role
4. Create Project
	5. + to create project with standard template
	6. Dropdown select project template and create new project with selected template
7. Admin
	8. Amin role related entries
		9. Chat roles
		10. Assistants
		11. Files
		12. Vectors
		10. Project Templates
	11. User related entries
		12. Profile
		13. Feedback
		14. logout

## Main page
2. Create new chat (with response client)
3. Create new project
4. Table with last 4 chats
	5. In Table header link to chat overview page
	5. open a chat
5. Table with last 4 projects
	6. In Table header link to project overview page
	6. Open a project

Main Page.png

## Chat overview page
3. Go Back to Main Page Button
3. Table with all chats
4. Sorted by Date New to Old
5. 6 lines per page / paging enabled
7. open a chat by clicking the line in the table
8. Deleting a chat by clicking a trash symbol in the line

chat overview.png

## Chat Page
4. Go Back to Main Page Button
5. Go Back to Chat overview page Button
4. Left side chat window
5. Right side
	6. select role
	7. select vectors
	8. Add and list files for chat

chat.png

## Project overview page
1. Go Back to Main Page Button 
2. Table with all chats
4. Sorted by Date New to Old
5. 6 lines per page / paging enabled
7. open a chat by clicking the line in the table
8. Deleting a chat by clicking a trash symbol in the line

project overview.png

## Project Page
Projects combine chats and workers

project.png

## Worker
- Worker is thread with assistance
- Worker is only available in projects 
- this tread will always have project vectors and project files 

worker.png

## projects
- Project has a description
- Project has attached files
- Project has attached vectors
- vectors where automatically attached to chats
- files where automatically attached to chats and workers (threads)

# User Management
## Authentication
- Authentication with internal users
- Authentication and registration with replit, apple and microsoft

## user roles
- Basic User
- Advanced User
- Full User
- Admin User
In Version one of Orquestrix all users will have admin role


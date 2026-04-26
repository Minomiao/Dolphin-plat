# Change Log

## Requirements

+ Review the complete logic of `d:\codes\QuickAI\skills\powershell_executor\skill.py`
+ Check the main program's design for confirmation mechanism requests
+ Determine whether user confirmation is returned to AI or to skill
+ Modify confirmation operation to return value to skill instead of AI
+ Read and modify `d:\codes\QuickAI\skills\powershell_executor\skill.py` to handle confirmation operations through the main program
+ Continue with original logic after receiving confirmation
+ Commit changes
+ Push changes to remote repository
+ Create a new tag
+ Retry pushing tag if failed
+ Check modifications between current and previous tag
+ Create a document using + (add), - (delete), / (change) format
+ Add the document to .gitignore
+ Do not use hash mark headings except for tag records in the document
+ Record the document in English
+ Use + for additions, - for deletions, / for changes
+ Organize all requirements from previous context at the top of the change log in English

## v0.2.1 (2026-04-25)

+ Implement real-time streaming output for AI response content with typewriter effect in terminal
/ Separate thinking and response output to prevent interleaving in terminal display
+ Add new v4 models (deepseek-v4-flash, deepseek-v4-pro) with model registry system
+ Add deprecation tracking for legacy models (deepseek-chat/reasoner/coder → 2026-07-24)
+ Add deprecation warning on startup and in settings mode with remaining days countdown
+ Implement dual-layer work directory system (persisted config + AI temporary variable)
+ Make AI work directory actually switchable via set_work_directory with bounds validation
+ Support relative path navigation (..) to return to parent directory within work root
+ Auto-fallback to root work directory when path goes out of bounds instead of error
+ Keep AI work directory across messages within same conversation session
+ Extract _process_stream() common method to deduplicate ~110 lines of stream loops
+ Extract _process_tool_confirmation() to deduplicate ~360 lines of confirmation logic
+ Extract _execute_powershell_script() to centralize PowerShell execution with timeouts
+ Clean up RequestManager: remove 4 dead handler methods and unused create_request_output
/ Update settings mode model selection to dynamic listing from model registry
/ Change default model from deepseek-chat to deepseek-v4-flash across all modules
/ Reset work directory only on /clear, /new, /load and startup, not every message
/ Rewrite README with quick start first, complete execution flow, and confirmation workflow
/ Reduce chat.py from 989 lines to 691 lines through method extraction

**modules/chat.py**:
  / Refactor stream processing into _process_stream() shared method
  + Add _process_tool_confirmation() for unified USER_INPUT/CONFIRMATION/SKILL_CONFIRMATION handling
  + Add _execute_powershell_script() for centralized PowerShell script execution
  / Remove dead code related to RequestManager pending_requests iteration
  / Remove reset_work_directory() calls from chat() and chat_stream() (mid-conversation)
  / Add reset_work_directory() calls to clear_history() and load_conversation()

**modules/config.py**:
  + Add MODEL_REGISTRY with 5 models, deprecation metadata, and replacement mapping
  + Add get_available_models() to return model list for dynamic UI generation
  + Add check_model_deprecation() with days-left calculation and warning message
  / Update default model from deepseek-chat to deepseek-v4-flash

**modules/request_manager.py**:
  + Add _ai_work_directory module-level variable for AI temporary directory
  + Add set/get/reset_ai_work_directory() and get_persisted_work_directory() functions
  / Modify _handle_config_request('load') to overlay AI work directory on config result
  - Remove _handle_user_input_request, _handle_confirmation_request (dead code)
  - Remove _handle_skill_confirmation, _handle_console_output (dead code)
  - Remove create_request_output (unused)

**skills/file_manager/skill.py**:
  / Fix set_work_directory to use persisted directory as base, AI current as relative resolver
  + Add out-of-bounds auto-fallback to root directory instead of returning error
  + Add from pathlib import Path (previously missing import)

**main.py**:
  / Rewrite settings_mode model selection to dynamic registry-based listing
  + Add deprecated model section with unified deprecation message
  + Add deprecation check on program startup with colored warning
  / Update response output from batch to streaming (response_chunk + response_end events)
  / Add thinking_end before response starts to prevent interleaving
  / Update callback with response_chunk and response_end event handlers

**README.md**:
  / Restructure with quick start at top, complete execution flow documentation
  + Add model list with deprecation dates
  + Add work directory dual-layer mechanism documentation
  + Add confirmation operation flow documentation with extracted method details
  + Add streaming output section
  / Update architecture to reflect cleaned-up module responsibilities

## v0.2.0-alpha (2026-04-22)

+ Implement request manager for skills and plugins
+ Add file operation module for centralized file operations
+ Implement prompt manager module for centralized system prompt management
+ Implement dialog-level backup management with single backup per file per conversation
/ Update file reader and file operation to use consistent line numbering
/ Improve work directory management: temporary switching, reset on new conversation, and clear subfolder usage instructions
+ Enhance request manager with console output support
/ Update README with architecture documentation and command reference
- Remove confirm_action function from user_input plugin
- Remove package_plugin.py build script
- Remove web-related files (main_server.py and Web-electron)
- Remove unused quickai_chat.py and quickai_client.py files

**modules/request_manager.py**:
  + Create new module for managing skill and plugin requests
  + Implement console output support
  + Provide centralized request handling

**modules/file_operation.py**:
  + Create new module for centralized file operations
  + Update skills to use request manager for file operations

**modules/prompt_manager.py**:
  + Create new module for centralized system prompt management

**modules/backup_manager.py**:
  + Implement dialog-level backup management
  + Support single backup per file per conversation

**skills/file_manager/skill.py**:
  / Update to use consistent line numbering
  / Improve work directory management

**plugins/user_input_plugin/**:
  - Remove confirm_action function

**README.md**:
  / Update with architecture documentation and command reference

/ Improve system architecture with centralized management modules
/ Enhance file operation consistency across skills
/ Simplify codebase by removing unused files
/ Improve work directory management and backup organization

## v0.1.4-alpha (2026-04-12)

+ Add async callback support for better web compatibility
/ Restrict work directory to subdirectories only
+ Add colorama library for terminal output coloring
/ Improve output readability with color coding
/ Modify main program to use async main function

**modules/chat.py**:
  + Implement async callback mechanism
  + Add _call_callback method to support both sync and async callbacks
  + Modify chat and chat_stream methods to async
  + Update tool execution to use async calls

**skills/file_manager/skill.py**:
  / Restrict work directory to subdirectories only
  / Default to relative path resolution
  + Add path format hints for AI
  / Remove confirmation requirement for directory changes

**main.py**:
  + Add colorama library integration
  + Implement async main function
  / Add color coding for different output types
  + Initialize colorama for cross-platform support

**requirements.txt**:
  + Add colorama>=0.4.6 dependency

/ Improve terminal output readability with color coding
/ Enhance web compatibility with async callbacks
/ Strengthen security by restricting work directory scope

## v0.1.3-alpha (2026-04-06)

+ Add plugin skill loader functionality
+ Create user input plugin for requesting user information
/ Modify main program to support plugin skills
+ Implement manifest.json based skill information loading
+ Add prompt directory and prompts.json for skill prompts

**modules/plugin_skill_loader.py**:
  + Create new module for loading plugin skills from ZIP files
  + Implement manifest.json parsing
  + Support skill information loading from manifest.json
  + Add error handling and logging

**modules/chat.py**:
  + Integrate plugin skill loader
  + Add plugin tools to available tools list
  + Support plugin skill calls

**main.py**:
  + Add plugin skill management
  + Support enabling/disabling plugin skills
  + Display plugin skills in skill list

**plugins/user_input_plugin/**:
  + Create user input plugin
  + Implement request_user_input function
  + Implement confirm_action function
  + Add manifest.json for skill information
  + Add prompt/prompts.json for skill prompts

/ Improve plugin architecture, separate skill info from code
+ Support plugin skill discovery and loading
/ Enhance system extensibility through plugins

## v0.1.2-alpha (2026-03-30)

/ Refactor PowerShell executor confirmation mechanism to use standard confirmation flow
+ Improve skill operation guide documentation, add backup manager usage instructions
/ Optimize main program confirmation handling logic, support confirmed parameter passing

**skills/powershell_executor/skill.py**:
  + Add `confirmed` parameter to support execution after confirmation
  / Return confirmation request on first call, execute script after confirmation
  - Remove direct print() and input() calls
  + Keep complete script content in logs

**modules/chat.py**:
  + Add confirmed parameter in all three confirmation handling locations
  + Re-call skill to execute actual operation after user confirmation
  / Optimize confirmation handling process

**skills/SKILL_OPERATION_GUIDE.md**:
  + Add backup manager usage guide
  + Provide detailed code examples and usage instructions
  + Expand document structure

/ Unify confirmation mechanism design, consistent with other skills
+ Support confirmation flow for web version
/ Avoid code duplication, improve maintainability
/ Improve logging, enhance system traceability

## v0.1.1-alpha

/ Fix parameter truncation issue, increase max_tokens setting
/ Improve error handling, provide clearer error messages
/ Increase tool call iteration limit

## v0.1.0-alpha

+ Initial version release
+ Implement basic chat functionality
+ Integrate PowerShell executor skill
+ Add file management functionality
+ Implement backup mechanism
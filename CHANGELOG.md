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
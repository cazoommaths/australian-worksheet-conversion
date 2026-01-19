# Complete Beginner's Guide to Claude Code

## What is Claude Code?

Claude Code is a command-line tool that lets Claude (the AI) write and run code directly on your computer. Instead of copying code from a chat and pasting it into files, Claude Code does everything for you - it creates files, runs scripts, fixes errors, and builds entire projects.

Think of it like having a developer assistant who can actually touch your keyboard.

---

## Step 1: Install Claude Code

### On Mac (Terminal)

Open Terminal (press Cmd + Space, type "Terminal", press Enter) and run:

```bash
npm install -g @anthropic-ai/claude-code
```

If you don't have npm, first install Node.js from: https://nodejs.org/

### On Windows (Command Prompt or PowerShell)

Open Command Prompt or PowerShell and run:

```bash
npm install -g @anthropic-ai/claude-code
```

If you don't have npm, first install Node.js from: https://nodejs.org/

### Verify Installation

After installing, check it worked:

```bash
claude --version
```

You should see a version number like `1.0.0` or similar.

---

## Step 2: Set Up Your API Key

Claude Code needs your Anthropic API key to work.

1. Go to: https://console.anthropic.com/
2. Sign in (or create an account)
3. Go to "API Keys" section
4. Click "Create Key"
5. Copy the key (it starts with `sk-ant-...`)

Now set it up on your computer:

### On Mac/Linux

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

To make it permanent, add that line to your `~/.zshrc` or `~/.bashrc` file.

### On Windows

```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Or add it to your System Environment Variables permanently.

---

## Step 3: Create Your Project Folder

Navigate to where you want your project, then create and enter it:

```bash
# Go to your Documents folder (or wherever you want)
cd ~/Documents

# Create the project folder
mkdir cazoom-au-converter

# Go into it
cd cazoom-au-converter
```

---

## Step 4: Add the CLAUDE.md File

The CLAUDE.md file tells Claude Code what your project is about. It's like a brief for the AI.

1. Create a file called `CLAUDE.md` in your project folder
2. Copy the content from the CLAUDE.md I created for you
3. Save it

You can do this manually or ask Claude Code to do it:

```bash
claude "Create the project structure with empty folders"
```

---

## Step 5: Start Using Claude Code

Now you're ready! Here's how to use it:

### Basic Command

```bash
claude "your instruction here"
```

### Examples for Your Project

**Ask Claude to set up the project:**
```bash
claude "Read the CLAUDE.md file and set up the initial project structure with all the necessary folders and files"
```

**Ask Claude to create a script:**
```bash
claude "Create a Python script that reads a CSV file of worksheets and downloads the first 10 PDFs from their Dropbox links"
```

**Ask Claude to extract PDF information:**
```bash
claude "Write a script to extract all text from a PDF file and identify the year level, topic, and any UK-specific terminology"
```

**Ask Claude to fix an error:**
```bash
claude "I got this error when running the script: [paste error here]. Please fix it."
```

---

## Step 6: Understanding How Claude Code Works

When you give Claude Code an instruction, it:

1. **Reads your project** - It looks at CLAUDE.md and your existing files
2. **Plans the work** - It figures out what needs to be done
3. **Writes code** - It creates or modifies files
4. **Runs the code** - It executes scripts and commands
5. **Fixes problems** - If something breaks, it tries to fix it
6. **Reports back** - It tells you what it did

### What You'll See

Claude Code shows you:
- What files it's creating/editing
- What commands it's running
- Any errors and how it's fixing them
- The final result

### Approving Actions

By default, Claude Code asks permission before doing certain things (like installing packages or running commands). You can:
- Type `y` to approve
- Type `n` to reject
- Type `a` to approve all similar actions

---

## Step 7: Your First Session

Here's a complete first session for your project:

```bash
# 1. Navigate to your project
cd ~/Documents/cazoom-au-converter

# 2. Start Claude Code and ask it to set up everything
claude "I have a CLAUDE.md file in this folder. Please read it and:
1. Create all the necessary folders (config, scripts, data/input, data/output)
2. Create a requirements.txt with the Python packages we need
3. Create the config/terminology.json file with UK to Australian term mappings
4. Create the config/au_curriculum_mapping.json file with year level mappings"

# 3. Once that's done, ask it to create the first script
claude "Create a Python script called extract_pdf_info.py that:
- Takes a PDF file path as input
- Extracts all the text from the PDF
- Identifies the year level (e.g., Year 5)
- Identifies the topic (e.g., Fractions)
- Returns this information as a dictionary"

# 4. Test with a sample PDF (you'll need to add one to data/input first)
claude "Run the extract_pdf_info.py script on the first PDF in data/input and show me what it extracts"
```

---

## Common Commands Reference

| What You Want | Command |
|---------------|---------|
| Start a chat session | `claude` (then type your questions) |
| Single instruction | `claude "do this thing"` |
| Run in current folder | `cd your-folder` then `claude` |
| See what files exist | `claude "list all files in this project"` |
| Explain code | `claude "explain what this script does"` |
| Fix an error | `claude "fix this error: [paste error]"` |
| Continue previous work | `claude --continue` |

---

## Tips for Success

### 1. Be Specific
❌ "Make a script"
✅ "Create a Python script that downloads a PDF from a Dropbox link and saves it to the data/input folder"

### 2. Work in Steps
Don't ask for everything at once. Break it into phases:
1. First: "Set up the folder structure"
2. Then: "Create the download script"
3. Then: "Create the extraction script"
4. Then: "Create the mapping script"

### 3. Test with Small Batches
Start with 5-10 worksheets, not hundreds. Make sure it works before scaling.

### 4. Keep CLAUDE.md Updated
When you learn new things about the project, update CLAUDE.md. Claude Code reads it every time.

### 5. Use Clear File Names
- `01_download.py` (runs first)
- `02_extract.py` (runs second)
- `03_map.py` (runs third)

---

## Troubleshooting

### "Command not found: claude"
- Make sure Node.js and npm are installed
- Run `npm install -g @anthropic-ai/claude-code` again
- Close and reopen your terminal

### "Invalid API key"
- Double-check your API key is correct
- Make sure you set the environment variable
- Check you have credits in your Anthropic account

### "Permission denied"
- On Mac/Linux, you might need: `sudo npm install -g @anthropic-ai/claude-code`

### Claude Code is slow
- Large projects take longer to analyse
- Complex tasks need more time
- Check your internet connection

---

## What's Next?

Once you're comfortable with the basics:

1. **Add your data**: Export your worksheet list from Google Sheets to `data/worksheets.csv`
2. **Download samples**: Get 10 test PDFs from Dropbox into `data/input`
3. **Run extraction**: Ask Claude Code to extract information from all PDFs
4. **Review mappings**: Check the UK → Australian mappings make sense
5. **Iterate**: Adjust and improve based on results

---

## Getting Help

- Claude Code docs: https://docs.anthropic.com/claude-code
- Anthropic support: https://support.anthropic.com
- Or just ask Claude Code: `claude "how do I..."`

Good luck with your Australian worksheet conversion project! 🦘

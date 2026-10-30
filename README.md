# MAPS-Code: An Multi-Agentic LLMs Code Generation Multi Files

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#framework-architecture">Architecture</a> •
  <a href="#repository-structure">Structure</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#license">License</a>
</p>

---

## 📖 Overview

**MAPS-Code** is an adversarial multi-agent code generation framework designed to improve the effectiveness, correctness, and robustness of multi-file code generation. By orchestrating specialized agents (Planner, Coder, Tester, and Reviewer) alongside an advanced GraphRAG and sandbox execution pipeline, the system intelligently handles complex programming tasks across Python, Java, and C.

---

## 🏗️ Framework Architecture

The framework consists of distinct specialized roles collaborating through an iterative self-correction feedback loop:

1. **Planner Agent:** Makes strategic plans and extracts relevant codebase context by leveraging GraphRAG.
2. **Coder Agent:** Generates initial code implementations based on tasks, target languages, and execution plans.
3. **Tester Agent:** Independently designs and generates rigorous unit test cases to verify the codebase.
4. **Reviewer Agent:** Investigates errors using function calling and coordinates feedback allocation for iterative refinement.
5. **Sandbox Engine:** Safely executes and tests generated code across multiple language drivers (Python, Java, C).

---

## 📁 Repository Structure

```text
PyMultiAgent/
├── multi_agent_system/               
│   ├── agents/
│   │   ├── __init__.py           # Core agent module
│   │   ├── base_agent.py         # LLM protocol management, response cleaning & JSON extraction
│   │   ├── coder_agent.py        # Code synthesis based on task, language, and plans
│   │   ├── planner_agent.py      # Planning & codebase extraction using GraphRAG
│   │   ├── reviewer_agent.py     # Error investigation & agent feedback allocation
│   │   └── tester_agent.py       # Test case generation for code verification
│   ├── rag/
│   │   ├── __init__.py           # RAG pipeline module
│   │   ├── ast_extractor.py      # Multi-language AST parsing & extraction
│   │   ├── graph_store.py        # Vector and graph database management
│   │   └── rag_pipeline.py       # Semantic codebase search pipeline for the Planner
│   ├── sandbox/    
│   │   ├── drivers/  
│   │   │   ├── __init__.py       # Language driver factory
│   │   │   ├── base.py           # Abstract base class for execution drivers
│   │   │   ├── c_driver.py       # C execution driver
│   │   │   ├── java_driver.py    # Java execution driver
│   │   │   └── python_driver.py  # Python execution driver
│   │   ├── framework/
│   │   │   ├── c/
│   │   │   │   └── minunit.h     # Minimal Unit Testing Framework for C
│   │   │   └── junit/            # Java Unit Testing Framework
│   │   ├── __init__.py           # Sandbox module
│   │   └── engine.py             # Sandbox execution pipeline
│   ├── tools/ 
│   │   ├── __init__.py           # System utility tools
│   │   ├── language_detector.py  # Python, C, and Java language detector
│   │   └── workspace_tools.py    # File reading and workspace search tools
│   ├── config.py                 # System configuration parameters
│   ├── coordinator.py            # Execution cycle coordinator & self-correction loop
│   ├── main.py                   # Internal CLI entrypoint
│   ├── memory.py                 # Shared agent memory management
│   └── schemas.py                # Data structure schemas
├── run_mas.py                    # Main CLI entry point
├── requirements.txt              # Required Python dependencies
└── README.md
```
**Architect of system:**
![Pipeline](images/pipeline.png "Pipeline of project")

⚙️ Installation
Clone the repository:

Bash
git clone https://github.com/Ctam0504/MAPS-Code
cd MAPS-Code

install dependencies:

Bash
pip install -r requirements.txt

Usage
1. Run via CLI
To execute the multi-agent system from the command line:

Bash
python run_mas.py

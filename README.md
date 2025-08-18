# EDINET API Tools :jp:

A practical toolkit for analyzing Japanese financial disclosures programmatically.

This project provides a set of tools for interacting with Japan's [EDINET](https://disclosure2.edinet-fsa.go.jp/) (Electronic Disclosure for Investors Network) API v2. It focuses on downloading, processing, and performing **structured analysis** of financial disclosure documents using the `llm` library.

Leverage the power of Large Language Models to extract specific, structured insights from unstructured financial text.

## Features

- 📅 Retrieve and filter disclosure documents by type and date range using the EDINET API
- 📂 Download and process ZIP files containing XBRL-derived CSV data
- 🧹 Clean and process text data from financial disclosures
- 📊 Structured Analysis: Analyze processed disclosure data using LLMs (via the `llm` library) to extract information conforming to predefined schemas.
- 🤖 Flexible LLM Backend: Use any LLM supported by the `llm` library (OpenAI, Claude, Gemini, local models, etc.) by changing configuration.
- ✅ **Well Tested**: Comprehensive test suite with pytest
- 🪵 Detailed Logging: Provides visibility into the data fetching, processing, and analysis steps.

## Requirements

- Python 3.9+ (Required by the `llm` library and recent dependencies)
- EDINET API key
- LLM API key (Optional for fetching EDINET data, but required by the LLM analysis features. This could be an OpenAI key, Anthropic key, etc., depending on the `llm` model chosen).
- Necessary LLM plugins installed if using models other than the default OpenAI ones.

## Installation

1.  Clone this repository:
    ```bash
    git clone https://github.com/matthelmer/edinet-api-tools.git
    cd edinet-tools
    ```

2.  Create and activate a virtual environment:
    -   On macOS and Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    -   On Windows:
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  Install required packages (this includes the `llm` library and its dependencies):
    ```bash
    pip install -r requirements.txt
    ```

4.  Install any `llm` plugins needed for the specific LLMs you want to use (e.g., for Claude, Gemini, local models):
    ```bash
    llm install llm-anthropic # Example for Anthropic models
    llm install llm-gemini    # Example for Google Gemini models
    llm install llm-gpt4all   # Example for local GPT4All models
    # See https://llm.datasette.io/en/stable/plugins/directory.html for more
    ```

5.  Set up environment variables:
    -   Create a `.env` file in the project root.
    -   Add your API keys and specify your desired LLM:
        ```dotenv
        EDINET_API_KEY=<your_edinet_api_key>

        # --- LLM Configuration ---
        # Use LLM_API_KEY OR a specific key like OPENAI_API_KEY depending on your LLM
        # If using OpenAI, OPENAI_API_KEY is sufficient.
        # If using other models via llm plugins, check their documentation.
        # Example for OpenAI:
        OPENAI_API_KEY=<your_openai_api_key>
        LLM_MODEL=gpt-5-mini # Or 'claude-3.5-sonnet', 'gemini-2.5-flash-04-17', etc.
        LLM_FALLBACK_MODEL=claude-4-sonnet # Optional: A model to try if LLM_MODEL fails

        # If using Azure OpenAI:
        # AZURE_OPENAI_API_KEY=<your_azure_openai_api_key>
        # AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
        # AZURE_OPENAI_API_VERSION=<your_azure_openai_api_version>
        # AZURE_OPENAI_DEPLOYMENT=<your_azure_openai_deployment_name>
        # Ensure LLM_MODEL is set to your Azure deployment name if using this.
        ```
        You can also use `llm keys set <key_name>` to manage keys independently for LLM plugins. Check the specific plugin documentation or `llm models --options` for details on how each model expects its key. Setting the key in the `.env` file using the expected environment variable (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) is often the simplest approach that works with the `llm` library.

6.  Ensure your virtual environment (venv) is activated whenever you use these tools.

## Usage

Run the demo script to see the tools in action:

```bash
python demo.py
```

This will:
- Fetch documents of supported types (Semi-Annual, Extraordinary Reports) from the most recent day with filings.
- Download the corresponding ZIP files.
- Process the CSV data within the ZIPs into a structured format.
- Run multiple analysis tools (configured in `llm_analysis_tools.py`) using your specified LLM to generate structured summaries and insights from the processed data.
- Print the analysis results to the console.

## Main Components

-   `edinet_tools.py`: Functions for interacting with the EDINET API (fetching lists, downloading documents), includes retry logic and error handling.
-   `utils.py`: Utility functions for file processing (encoding detection, CSV reading) and text cleaning. Handles extracting data from the complex ZIP archive structure.
-   `document_processors.py`: Contains classes (`BaseDocumentProcessor`, `ExtraordinaryReportProcessor`, `SemiAnnualReportProcessor`, `GenericReportProcessor`) for processing raw CSV data into a structured dictionary format, tailored to different document types.
-   `llm_analysis_tools.py`: Defines the framework for LLM-based structured analysis using Pydantic schemas and the `llm` library. Contains specific tools (like `OneLinerTool`, `ExecutiveSummaryTool`) and the dispatcher function `analyze_document_data`.
-   `config.py`: Handles environment variable loading and defines global configurations like supported document types and default LLM models.
-   `logging_config.py`: Sets up basic logging for the application.
-   `demo.py`: Demonstration script showing the tool's capabilities and orchestrating the workflow.

## Testing

Run the test suite to verify everything works:

```bash
pytest
```

Or run specific test categories:
```bash
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests only
```

## Customization

-   **Analysis Tools:** Modify `llm_analysis_tools.py` to create new analysis tools. Define a Pydantic schema for the desired output, create a class inheriting from `BasePromptTool`, implement `create_prompt` and `format_to_text`, and add your new tool to the `TOOL_MAP`.
-   **Document Processing:** Add new classes inheriting from `BaseDocumentProcessor` in `document_processors.py` to handle specific document types (beyond 160 and 180). Add your processor to the `processor_map` in `document_processors.process_raw_csv_data`.
-   **Supported Document Types:** Update the `SUPPORTED_DOC_TYPES` dictionary in `config.py`.

## Contributing

This project welcomes contributions. Please ensure tests pass before submitting PRs:

```bash
pytest
```

## Disclaimer

This project is an independent tool and is not affiliated with, endorsed by, or in any way officially connected with the Financial Services Agency (FSA) of Japan or any of its subsidiaries or affiliates.

We are grateful to the Financial Services Agency for creating and maintaining the EDINET v2 API.

The official EDINET website: [https://disclosure2.edinet-fsa.go.jp/](https://disclosure2.edinet-fsa.go.jp/).

This software is provided "as is" for informational purposes only. The creator assumes no liability for errors, omissions, or any consequences of using this software. This tool does not provide financial advice. Users are solely responsible for verifying information and for any decisions made based on it. Use at your own risk.

## License

This project is licensed under the MIT License.

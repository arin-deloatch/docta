"""
QA Test Set Generator Example

This script demonstrates how to use the ragas library to automatically generate
question-answer pairs from documentation. This is particularly useful for:

- Creating evaluation datasets for RAG (Retrieval-Augmented Generation) systems
- Building QA test sets from technical documentation
- Synthetic data generation for model evaluation

The example uses Google's Generative AI models (Gemini) for both LLM and embedding
tasks, but can be adapted to use other providers supported by ragas.

Requirements:
    - GOOGLE_API_KEY environment variable must be set
    - Optional: LLM_MODEL (default: gemini-2.5-flash)
    - Optional: EMBEDDING_MODEL (default: gemini-embedding-2-preview)

Usage:
    export GOOGLE_API_KEY=your_api_key_here
    python examples/qa_generator.py

Output:
    Generates and displays synthetic QA pairs with metadata including:
    - Question/user input
    - Reference answer/ground truth
    - Query style and length
    - Persona and synthesizer information
"""

import os
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import SingleHopSpecificQuerySynthesizer                                                       

# ============================================================================
# Configuration
# ============================================================================

# Google GenAI API credentials and model selection
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")

if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY environment variable is required. "
        "Get one at: https://aistudio.google.com/app/apikey"
    )

print("Using Google Generative AI")
print(f"  LLM: {LLM_MODEL}")
print(f"  Embeddings: {EMBEDDING_MODEL}")


# ============================================================================
# Model Initialization
# ============================================================================

# Initialize the LLM for generating questions and answers
llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    google_api_key=GOOGLE_API_KEY,
)

# Initialize embeddings model for semantic understanding of documents
embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBEDDING_MODEL,
)

# Wrap LangChain components for ragas compatibility
# ragas uses these wrappers to interface with various LLM providers
generator_llm = LangchainLLMWrapper(llm)
generator_embeddings = LangchainEmbeddingsWrapper(embeddings)


# ============================================================================
# Sample Documents
# ============================================================================

# In a real-world scenario, these documents would be loaded from your actual
# documentation sources (PDFs, markdown files, web pages, etc.)
# This example uses sample content about Identity Management 2FA authentication

docs = [
    # Document 1: Overview of 2FA in Identity Management
    Document(
        page_content=(
            "Identity Management (IdM) administrators can enable two-factor "
            "authentication (2FA) for IdM users either globally or individually. "
            "Two-factor authentication adds an extra layer of security to user accounts "
            "by requiring two forms of verification: something the user knows (password) "
            "and something the user has (OTP token). The user enters the one-time password "
            "(OTP) after their regular password on the command line or in the dedicated "
            "field in the Web UI login dialog, with no space between these passwords. "
            "IdM supports both hardware tokens and software-based OTP generation through "
            "mobile applications like Google Authenticator or FreeOTP. Administrators can "
            "enforce 2FA policies at the user level or globally across the entire domain. "
            "When 2FA is enabled, users must first sync their token with the IdM server "
            "before they can successfully authenticate. The OTP codes are time-based and "
            "rotate every 30 seconds, providing enhanced security against replay attacks "
            "and unauthorized access attempts."
        ),
        metadata={"source": "idm_2fa_setup_guide", "chapter": "authentication"},
    ),
    # Document 2: Configuration procedures for 2FA
    Document(
        page_content=(
            "Configuring two-factor authentication in Red Hat Identity Management requires "
            "several steps. First, administrators must enable OTP authentication on the IdM "
            "server using the ipa config-mod command with the --enable-otp flag. Next, "
            "individual users can be configured for 2FA using the ipa user-mod command with "
            "the --user-auth-type=otp option. The Web UI provides an alternative graphical "
            "interface for enabling 2FA on user accounts through the Users section. After "
            "enabling 2FA for a user, they must enroll their token by logging into the Web UI "
            "and scanning the provided QR code with their authenticator app. Hardware tokens "
            "can also be registered by entering the token's seed value and serial number. "
            "Administrators can view all registered tokens for a user and can delete tokens "
            "if they are lost or compromised. Best practices recommend backing up token seeds "
            "in a secure location and training users on proper token management procedures. "
            "Password reset procedures must be adapted when 2FA is enabled, as users will need "
            "to provide both factors during the reset process."
        ),
        metadata={"source": "idm_2fa_admin_guide", "chapter": "configuration"},
    ),
    # Document 3: Integration with authentication backends
    Document(
        page_content=(
            "Identity Management integrates with various authentication backends and protocols. "
            "The system supports Kerberos for single sign-on, LDAP for directory services, and "
            "can integrate with external identity providers through SAML and OAuth protocols. "
            "When implementing 2FA, it's important to understand how it interacts with these "
            "authentication mechanisms. Kerberos tickets can be obtained after successful 2FA "
            "verification, and the OTP is validated before the ticket-granting ticket is issued. "
            "SSH access can be configured to require 2FA by modifying the SSH configuration and "
            "setting ChallengeResponseAuthentication to yes. Web applications that authenticate "
            "through IdM will automatically enforce 2FA requirements if configured on the user "
            "account. The authentication flow follows a standard challenge-response pattern where "
            "the server requests both password and OTP, validates them independently, and only "
            "grants access when both factors are verified correctly. Failed authentication attempts "
            "are logged and can trigger account lockout policies if too many failures occur within "
            "a specified time window."
        ),
        metadata={"source": "idm_authentication_architecture", "chapter": "integration"},
    ),
]


# ============================================================================
# Test Set Generation
# ============================================================================

query_distribution = [                                                                                                         
      (SingleHopSpecificQuerySynthesizer(llm=generator_llm), 1.0)                                                                
  ]

# Initialize the test set generator with our configured LLM and embeddings
# The generator uses these models to:
# 1. Understand document semantics (via embeddings)
# 2. Generate diverse, realistic questions (via LLM)
# 3. Create reference answers based on document content (via LLM)
generator = TestsetGenerator(
    llm=generator_llm,
    embedding_model=generator_embeddings,
)

# Generate synthetic QA pairs from the documents
# testset_size: number of QA pairs to generate
# The generator will create questions of varying:
# - Complexity (simple, reasoning, multi-hop)
# - Length (short, medium, long)
# - Style (factual, analytical, comparative)
testset = generator.generate_with_langchain_docs(
    documents=docs,
    testset_size=10,
    query_distribution=query_distribution,
)


# ============================================================================
# Display Results
# ============================================================================

print("\n" + "=" * 80)
print("GENERATED QA SETS")
print("=" * 80 + "\n")

# Convert to pandas DataFrame for structured display and easy export
df = testset.to_pandas()

# Display each generated QA pair with metadata
# The metadata helps understand how the question was synthesized
for idx, row in df.iterrows():
    print(f"QA Pair #{idx + 1}")
    print("-" * 80)

    # The actual question that would be asked
    print(f"Question: {row['user_input']}")

    # The expected/reference answer based on the source documents
    print(f"\nGround Truth: {row['reference']}")

    # Metadata about how this QA pair was generated
    print(f"\nQuery Style: {row.get('query_style', 'N/A')}")
    print(f"Query Length: {row.get('query_length', 'N/A')}")
    print(f"Persona: {row.get('persona_name', 'N/A')}")
    print(f"Synthesizer: {row.get('synthesizer_name', 'N/A')}")

    print("\n" + "=" * 80 + "\n")
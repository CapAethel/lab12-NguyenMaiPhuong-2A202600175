"""
Mock LLM for development and testing.
Replace with actual OpenAI/Anthropic client in production.
"""
import time
import random
from typing import Dict, List


# Mock responses for different question types
MOCK_RESPONSES: Dict[str, List[str]] = {
    "hello": [
        "Hello! I'm your AI assistant. How can I help you today?",
        "Hi there! I'm ready to assist you with any questions you have.",
        "Greetings! What would you like to know?",
    ],
    "how": [
        "That's a great question! Here's how it works...",
        "Let me explain the process step by step...",
        "Here's a detailed guide on how to do that...",
    ],
    "what": [
        "That's an interesting question. Let me tell you about...",
        "Here's what you need to know about...",
        "Let me explain what that means...",
    ],
    "why": [
        "That's a thoughtful question. The reason is...",
        "Here's why that happens...",
        "Let me explain the reasoning behind this...",
    ],
    "default": [
        "That's a fascinating question! Based on my knowledge, I can tell you that...",
        "Interesting! Let me provide you with a comprehensive answer...",
        "Great question! Here's what I know about that topic...",
        "I'd be happy to help you with that. Here's my response...",
    ]
}


def classify_question(question: str) -> str:
    """Simple keyword-based question classification."""
    question_lower = question.lower().strip()

    if any(word in question_lower for word in ["hello", "hi", "hey", "greetings"]):
        return "hello"
    elif question_lower.startswith("how"):
        return "how"
    elif question_lower.startswith("what"):
        return "what"
    elif question_lower.startswith("why"):
        return "why"
    else:
        return "default"


def ask(question: str) -> str:
    """
    Mock LLM response function.
    Simulates API call latency and returns contextual responses.
    """
    # Simulate API latency (50-200ms)
    time.sleep(random.uniform(0.05, 0.2))

    question_type = classify_question(question)
    responses = MOCK_RESPONSES.get(question_type, MOCK_RESPONSES["default"])

    # Return random response from the category
    return random.choice(responses)


def estimate_tokens(text: str) -> int:
    """Rough token estimation (words * 1.3 for subwords)."""
    return int(len(text.split()) * 1.3)


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate cost in USD."""
    # GPT-4o-mini pricing (approximate)
    input_cost = (input_tokens / 1000000) * 0.15
    output_cost = (output_tokens / 1000000) * 0.60
    return input_cost + output_cost
#!/usr/bin/env python3
"""
Autonomous SEO Agent Worker (Compatibility Bridge)
Delegates directly to the deep content_generator module while maintaining
backward-compatible CLI and programmatic interfaces.
"""

import sys
from typing import Optional
from content_generator import (
    generate_article,
    ArticleGenerationResult,
    BaseLLMAdapter,
    LiveLLMAdapter,
    InMemoryLLMAdapter,
    get_llm_adapter,
    set_llm_adapter
)

def run_agent(user_id: Optional[str] = None) -> Optional[ArticleGenerationResult]:
    """
    Backward-compatible entrypoint delegating to content_generator.generate_article.
    """
    result = generate_article(tenant_id=user_id)
    if result.success:
        print(f"SUCCESS: Artikel baru berhasil dibuat dengan ID {result.article_id} untuk keyword '{result.keyword}'.")
        print(f"Title: {result.title}")
        print(f"Status: {result.status} (tersimpan di database untuk direview)")
    else:
        print(f"FAILED: {result.error}")
    return result

if __name__ == '__main__':
    target_user = None
    if len(sys.argv) > 1 and sys.argv[1].startswith('--user-id='):
        target_user = sys.argv[1].split('=', 1)[1].strip()
    elif len(sys.argv) > 2 and sys.argv[1] == '--user-id':
        target_user = sys.argv[2].strip()
    run_agent(user_id=target_user)

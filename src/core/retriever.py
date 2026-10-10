"""
Hybrid retriever: dense pgvector + BM25 re-ranking + RRF merge.

Retrieval flow:
  1. Dense: pgvector cosine similarity search (top TOP_K_DENSE)
  2. BM25: score the dense results with BM25 against the query
  3. RRF: merge dense-rank and bm25-rank scores
  4. Return top TOP_K_FINAL documents
"""
from typing import List, Optional, Dict, Any, Tuple
from langchain_core.documents import Document
from langchain_postgres import PGVector
from rank_bm25 import BM25Okapi
from config.settings import settings
from core.embeddings import embeddings
import structlog

log = structlog.get_logger()

COLLECTION_NAME = "pico_embeddings"


def get_vector_store(connection_string: Optional[str] = None) -> PGVector:
    """Return a PGVector store instance."""
    conn = connection_string or settings.postgres_url_sync
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=conn,
        use_jsonb=True,
    )


class HybridRetriever:
    """
    Hybrid retrieval with dense pgvector + BM25 re-ranking + RRF.
    """

    def __init__(
            self,
            vector_store: PGVector,
            top_k_dense: int = settings.top_k_dense,
            top_k_final: int = settings.top_k_final,
            rrf_k: int = settings.rrf_k,
    ):
        self.vector_store = vector_store
        self.top_k_dense = top_k_dense
        self.top_k_final = top_k_final
        self.rrf_k = rrf_k

    def retrieve(
            self,
            query: str,
            workspace_id: str,
            user_id: Optional[str] = None,
            filename: Optional[str] = None,
    ) -> List[Document]:
        """Hybrid retrieval with metadata filtering."""
        filter_dict: Dict[str, Any] = {"workspace_id": workspace_id}
        if user_id:
            filter_dict["user_id"] = user_id
        if filename:
            filter_dict["filename"] = filename

        # 1. Dense retrieval
        try:
            dense_results: List[Tuple[Document, float]] = (
                self.vector_store.similarity_search_with_score(
                    query=query,
                    k=self.top_k_dense,
                    filter=filter_dict,
                )
            )
        except Exception as e:
            log.warning("dense_retrieval_failed", error=str(e))
            dense_results = []

        if not dense_results:
            return []

        docs = [doc for doc, _ in dense_results]

        # 2. BM25 re-ranking on dense results
        tokenized_corpus = [doc.page_content.lower().split() for doc in docs]
        tokenized_query = query.lower().split()

        try:
            bm25 = BM25Okapi(tokenized_corpus)
            bm25_scores_raw = bm25.get_scores(tokenized_query)
            bm25_ranks = {
                doc_idx: rank
                for rank, doc_idx in enumerate(
                    sorted(range(len(bm25_scores_raw)), key=lambda i: bm25_scores_raw[i], reverse=True)
                )
            }
        except Exception as e:
            log.warning("bm25_failed", error=str(e))
            bm25_ranks = {i: i for i in range(len(docs))}

        # 3. Dense ranks
        dense_ranks = {
            doc_idx: rank
            for rank, doc_idx in enumerate(
                sorted(range(len(dense_results)), key=lambda i: dense_results[i][1], reverse=True)
            )
        }

        # 4. RRF merge
        rrf_scores: Dict[int, float] = {}
        for doc_idx in range(len(docs)):
            dr = dense_ranks.get(doc_idx, len(docs))
            br = bm25_ranks.get(doc_idx, len(docs))
            rrf_scores[doc_idx] = (1 / (self.rrf_k + dr)) + (1 / (self.rrf_k + br))

        # Sort by RRF score descending
        top_indices = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)[
            : self.top_k_final
        ]

        result = [docs[i] for i in top_indices]
        log.info(
            "hybrid_retrieval_done",
            query_preview=query[:60],
            dense_count=len(dense_results),
            final_count=len(result),
        )
        return result


def build_retriever() -> HybridRetriever:
    vs = get_vector_store()
    return HybridRetriever(vector_store=vs)

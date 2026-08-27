import os
import chromadb
from openai import OpenAI
from sentence_transformers import CrossEncoder

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
rr_model = CrossEncoder("cross-encoder/ettin-reranker-68m-v1")
chroma_client = chromadb.PersistentClient(path='./chroma_db/test_db')
collection = chroma_client.get_or_create_collection(name="test_collection")
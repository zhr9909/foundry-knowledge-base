#!/usr/bin/env python3
import os, sys, json
os.environ["SURYA_MODEL_DIR"] = r"E:\\AgentProjects\\ai-solution-architect-lab\\surya_models"
from surya.settings import settings
settings.MODEL_CACHE_DIR = r"E:\\AgentProjects\\ai-solution-architect-lab\\surya_models"
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
pdf_path, out_path = sys.argv[1], sys.argv[2]
converter = PdfConverter(artifact_dict=create_model_dict())
rendered = converter(pdf_path)
text, metadata, images = text_from_rendered(rendered)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)
with open(out_path + ".img.json", "w") as f:
    json.dump({k: list(img.size) for k, img in images.items()}, f)

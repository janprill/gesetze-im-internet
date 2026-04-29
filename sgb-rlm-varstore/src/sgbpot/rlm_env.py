"""Exportierte RLM-Variablen für den PoT."""

from .varstore import SGBMemory

SGB = SGBMemory("varstore", scope="SGB")
SGG = SGBMemory("varstore", scope="SGG")
CARD = SGB.cards
TOPIC = SGB.topics
IDX = SGB.index
PACK = SGB.packer
TRACE = SGB.trace

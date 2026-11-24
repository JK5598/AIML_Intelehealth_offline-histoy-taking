"""Writes the Colab notebooks: finetune_medpsy.ipynb (notebook_cells.py)
and finetune_medpsy_unsloth.ipynb (notebook_unsloth_cells.py)."""
import json
import os

import notebook_cells
import notebook_unsloth_cells

HERE = os.path.dirname(os.path.abspath(__file__))


def write(cell_list, file_name):
    cells = []
    for kind, source in cell_list:
        lines = source.split("\n")
        source_lines = [line + "\n" for line in lines[:-1]] + [lines[-1]]
        cell = {"cell_type": kind, "metadata": {}, "source": source_lines}
        if kind == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)

    notebook = {
        "cells": cells,
        "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []},
                     "kernelspec": {"display_name": "Python 3", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4, "nbformat_minor": 0,
    }
    with open(os.path.join(HERE, file_name), "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    print(file_name, len(cells), "cells")


write(notebook_cells.CELLS, "finetune_medpsy.ipynb")
write(notebook_unsloth_cells.CELLS, "finetune_medpsy_unsloth.ipynb")

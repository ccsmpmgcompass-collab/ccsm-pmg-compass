"""The Informes analytics layer — one set of numbers, two renderers.

`model.build_report()` turns a scope and a period into a plain `ReportModel`
carrying no Streamlit and no ReportLab. `views/11_Informes.py` renders that to
the screen; `packet.py` renders it to the council PDF. Neither renderer does
arithmetic of its own, which is the only thing that keeps the printed packet
and the page on screen saying the same thing.

See PLAN-2026-09-21-informes.md §2 (decision 30).
"""

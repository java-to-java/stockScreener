"""Render data/predictions.json into a static dashboard at docs/index.html.

The template is plain HTML/CSS/JS with a single placeholder
(``__PREDICTIONS_JSON__``) that gets replaced with the predictions payload -
no server, no build step, so it works as-is on GitHub Pages (serve the
/docs folder) or opened directly as a local file.

Run from the repo root:

    python -m src.dashboard
"""
import json
import logging
import sys

import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def render(predictions_payload: dict) -> str:
    template = config.DASHBOARD_TEMPLATE_FILE.read_text()
    data_json = json.dumps(predictions_payload)
    # JSON can legally contain "</script>"; escape it so it can't break out
    # of the <script> tag it's embedded in.
    data_json = data_json.replace("</script>", "<\\/script>")
    return template.replace("__PREDICTIONS_JSON__", data_json)


def main() -> int:
    if not config.PREDICTIONS_FILE.exists():
        log.error("%s not found - run predict first.", config.PREDICTIONS_FILE)
        return 1

    payload = json.loads(config.PREDICTIONS_FILE.read_text())
    html = render(payload)

    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    config.DASHBOARD_OUTPUT_FILE.write_text(html)
    log.info("Wrote dashboard to %s", config.DASHBOARD_OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())

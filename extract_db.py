"""Extract database connection details from DOM"""
import sys, time
sys.stdout = open(1, 'w', encoding='ascii', errors='backslashreplace')
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    pg = browser.contexts[0].pages[0]

    pg.goto('https://dashboard.render.com/d/dpg-d8svlqurnols739v473g-a',
            wait_until='networkidle', timeout=30000)
    time.sleep(5)

    # Extract all form fields and their values
    fields = pg.evaluate('''() => {
        const inputs = document.querySelectorAll("input, textarea");
        const result = [];
        for (const inp of inputs) {
            const label = inp.previousElementSibling ?
                inp.previousElementSibling.textContent.trim() : "";
            const parentText = inp.closest("div") ?
                inp.closest("div").textContent.trim() : "";
            result.push({
                id: inp.id || "",
                type: inp.type || "",
                value: inp.value || "",
                placeholder: inp.placeholder || "",
                label: label,
                parentText: parentText.substring(0, 60)
            });
        }
        return result;
    }''')
    print('Form fields:')
    for f in fields:
        print(f'  id="{f["id"]}" type={f["type"]} val="{f["value"][:80]}" label="{f["label"][:40]}"')

    # Also check all divs with specific labels
    labels = pg.evaluate('''() => {
        const divs = document.querySelectorAll("div, span, label");
        const result = {};
        for (const el of divs) {
            const text = el.textContent.trim();
            if (["Hostname", "Port", "Database", "Username",
                 "Internal Database URL", "External Database URL",
                 "PSQL Command"].includes(text)) {
                // Get sibling or parent's input value
                const parent = el.closest("div");
                if (parent) {
                    const inp = parent.querySelector("input, textarea");
                    if (inp) {
                        result[text] = inp.value;
                    } else {
                        result[text] = "(no input found)";
                    }
                }
            }
        }
        return result;
    }''')
    print('\nValues by label:')
    for k, v in labels.items():
        print(f'  {k}: {v}')

    browser.close()

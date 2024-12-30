---
project: test-1
created_at: 2024-12-30 09:21:19.188877+00:00
---

>> Add items to the todo list and mark some as completed
> - GIVEN:
>   - page url: `https://demo.playwright.dev/todomvc/`
> - USE a browser
> - Fill "do the washing" into the input whose placeholder is "What needs to be done?" and press Enter
> - Fill "water the plants" and press Enter
> - Click the checkbox of "do the washing"
> - Click the "Active" link
> - Verify the list item "water the plants" exists
> - Click the "Completed" link
> - Verify the list item "do the washing" exists

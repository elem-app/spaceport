---
project: spaceport-on-wiki
created_at: 2024-12-29 17:32:04.171934+00:00
---

Wikipedia should have a page about "spaceport".

>> Searching for "spaceport" yields a Wikipedia page
> - GIVEN:
>   - Wikipedia homepage: https://en.wikipedia.org/wiki/Main_Page
> - USE a browser
> - Go to the Wikipedia homepage
> - Input "spaceport" into the search bar and click the search button
> - Verify the new page's heading contains "spaceport"
````py .test
# GIVEN:
#   - Wikipedia homepage: https://en.wikipedia.org/wiki/Main_Page
wiki_url = "https://en.wikipedia.org/wiki/Main_Page"

# USE a browser
T.use("browser")

# Go to the Wikipedia homepage
T.goto_url("browser//", wiki_url)

# Input "spaceport" into the search bar and click the search button
T.type_text('gui//input[label like "search"]', "spaceport")
T.click('gui//button[label like "search"]')

# Verify the new page's heading contains "spaceport"
assert T.has_some('gui//heading[label like "spaceport"]'), "Expected to find heading containing 'spaceport'"
````

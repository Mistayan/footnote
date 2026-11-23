//! Markdown made for search (#634): a link keeps its text and loses its target, an image keeps its alt text, and
//! rustdoc chrome (`Run code`, `§` anchors, `Copy item path`) goes. Measured on the Rust std crawl of 2026-11-23, link
//! targets were 29% of `struct.Vec` and 38% of `struct.VecDeque`: they filled the chunk budget and the embedder's
//! window with paths. Fenced code is left as is.

/// Link texts dropped with their link: page chrome, not content.
const CHROME_LINKS: [&str; 2] = ["Run code", "§"];

pub fn search_markdown(md: &str) -> String {
    let mut out = String::with_capacity(md.len());
    let mut fence = false;
    for line in md.lines() {
        let t = line.trim_start();
        if t.starts_with("```") || t.starts_with("~~~") {
            fence = !fence;
            out.push_str(line);
        } else if fence {
            out.push_str(line);
        } else {
            let l = strip_links(line);
            out.push_str(l.replace(" Copy item path", "").trim_end());
        }
        out.push('\n');
    }
    out
}

/// `[text](target "title")` -> `text`, `![alt](src)` -> `alt`. Inline code spans are copied untouched.
fn strip_links(line: &str) -> String {
    let b: Vec<char> = line.chars().collect();
    let mut out = String::with_capacity(line.len());
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            '`' => {
                // copy a code span whole so `a[i](x)` in code is not read as a link
                let ticks = b[i..].iter().take_while(|&&c| c == '`').count();
                let close = (i + ticks..b.len())
                    .find(|&j| b[j..].iter().take_while(|&&c| c == '`').count() == ticks);
                let end = close.map_or(b.len(), |j| j + ticks);
                out.extend(&b[i..end]);
                i = end;
            }
            '[' | '!' => {
                let open = if b[i] == '!' { i + 1 } else { i };
                if let Some((text, next)) = link_at(&b, open).filter(|_| b[open] == '[') {
                    let text = strip_links(&text);
                    if !CHROME_LINKS.contains(&text.trim()) {
                        out.push_str(&text);
                    }
                    i = next;
                } else {
                    out.push(b[i]);
                    i += 1;
                }
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    out
}

/// At `[`: the link text and the index after the closing `)`, when a `[...](...)` link starts here.
fn link_at(b: &[char], open: usize) -> Option<(String, usize)> {
    if b.get(open) != Some(&'[') {
        return None;
    }
    let mut depth = 0;
    let mut close = None;
    for (j, &c) in b.iter().enumerate().skip(open) {
        match c {
            '[' => depth += 1,
            ']' => {
                depth -= 1;
                if depth == 0 {
                    close = Some(j);
                    break;
                }
            }
            _ => {}
        }
    }
    let close = close?;
    if b.get(close + 1) != Some(&'(') {
        return None;
    }
    // the target ends at the `)` that balances, outside a quoted title
    let (mut depth, mut quoted) = (0, false);
    for (j, &c) in b.iter().enumerate().skip(close + 1) {
        match c {
            '"' => quoted = !quoted,
            '(' if !quoted => depth += 1,
            ')' if !quoted => {
                depth -= 1;
                if depth == 0 {
                    return Some((b[open + 1..close].iter().collect(), j + 1));
                }
            }
            _ => {}
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::search_markdown;

    #[test]
    fn links_keep_their_text_and_chrome_goes() {
        let md = "# Struct VecDeque Copy item path\n\
[std](../index.html)::[collections](index.html)\n\
#### **pub fn [with_capacity](#method.with_capacity)(capacity: [usize](../primitive.usize.html)) -> [VecDeque](struct.VecDeque.html \"struct std::collections::VecDeque\")<T>**\n\
Use [`push_back`](struct.VecDeque.html#method.push_back \"method (x)\") then ![logo](a(b).png).\n\
[Run code](https://play.rust-lang.org/?code=fn+main()+%7B%7D&edition=2024 \"Run code\")\n\
## Implementations[§](#implementations)\n\
`a[i](x)` stays, [ref][1] stays, [no target] stays\n\
```\nlet v = [x](y);\n```\n";
        assert_eq!(
            search_markdown(md),
            "# Struct VecDeque\n\
std::collections\n\
#### **pub fn with_capacity(capacity: usize) -> VecDeque<T>**\n\
Use `push_back` then logo.\n\
\n\
## Implementations\n\
`a[i](x)` stays, [ref][1] stays, [no target] stays\n\
```\nlet v = [x](y);\n```\n"
        );
    }
}

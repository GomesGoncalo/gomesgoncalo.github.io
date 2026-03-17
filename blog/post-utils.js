function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function buildToc(contentEl) {
  const headings = [...contentEl.querySelectorAll('h2, h3')];
  if (headings.length < 2) return;
  headings.forEach((h, i) => {
    if (!h.id) h.id = h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + (i ? `-${i}` : '');
  });
  const items = headings.map(h => {
    const sub = h.tagName === 'H3' ? ' class="toc-sub"' : '';
    return `<li${sub}><a href="#${h.id}">${escapeHtml(h.textContent)}</a></li>`;
  }).join('');
  const toc = document.createElement('details');
  toc.className = 'toc';
  toc.innerHTML = `<summary>Contents</summary><ol>${items}</ol>`;
  contentEl.insertAdjacentElement('beforebegin', toc);
}

function addCopyButtons(contentEl) {
  contentEl.querySelectorAll('pre').forEach(pre => {
    const code = pre.querySelector('code');

    const langMatch = code?.className?.match(/language-(\w+)/);
    if (langMatch && langMatch[1] !== 'plaintext') {
      const label = document.createElement('span');
      label.className = 'lang-label';
      label.textContent = langMatch[1];
      pre.appendChild(label);
    }

    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'copy';
    btn.addEventListener('click', () => {
      navigator.clipboard.writeText(code?.textContent || pre.textContent).then(() => {
        btn.textContent = 'copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('copied'); }, 2000);
      });
    });
    pre.appendChild(btn);
  });
}

function initProgressBar() {
  const bar = document.getElementById('reading-progress');
  window.addEventListener('scroll', () => {
    const total = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = total > 0 ? (window.scrollY / total * 100) + '%' : '0%';
  }, { passive: true });
}

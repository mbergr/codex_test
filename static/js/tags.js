(function () {
  const input = document.getElementById('tag-input');
  const addBtn = document.getElementById('tag-add');
  const chips = document.getElementById('tag-chips');
  const hidden = document.getElementById('tags-hidden');

  if (!input || !chips || !hidden) {
    return;
  }

  const tags = new Set();

  function render() {
    chips.innerHTML = '';
    tags.forEach((tag) => {
      const el = document.createElement('span');
      el.className = 'px-2 py-1 bg-emerald-900/40 border border-emerald-500/50 rounded-full text-xs flex items-center gap-2';
      el.innerHTML = `<span>#${tag}</span>`;
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.textContent = '×';
      removeBtn.className = 'hover:text-red-300';
      removeBtn.addEventListener('click', () => {
        tags.delete(tag);
        render();
      });
      el.appendChild(removeBtn);
      chips.appendChild(el);
    });
    hidden.value = Array.from(tags).join(',');
  }

  function addTag(value) {
    const tag = (value || '').trim();
    if (!tag) {
      return;
    }
    tags.add(tag);
    input.value = '';
    render();
  }

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addTag(input.value);
    }
  });

  addBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    addTag(input.value);
  });
})();

/* Chapter 11 teaching experiment. Does not call any analysis API. */
(() => {
  const panel = document.querySelector('.se-experiment');
  if (!panel) return;
  const slider = panel.querySelector('#se-n');
  const presets = [...panel.querySelectorAll('[data-se-n]')];
  const meter = panel.querySelector('[role="meter"]');
  const maxSE = 81.53 / Math.sqrt(10);
  function update() {
    const n = Number(slider.value);
    const se = 81.53 / Math.sqrt(n);
    panel.querySelector('#se-n-value').textContent = `${n}건`;
    panel.querySelector('#se-formula-n').textContent = n;
    panel.querySelector('#se-result').textContent = `${se.toFixed(2)}만원/㎡`;
    meter.setAttribute('aria-valuemax', maxSE);
    meter.setAttribute('aria-valuenow', se);
    meter.setAttribute('aria-valuetext', `${se.toFixed(2)}만원/㎡`);
    meter.firstElementChild.style.width = `${100 * se / maxSE}%`;
    presets.forEach(button => button.setAttribute('aria-pressed', Number(button.dataset.seN) === n));
  }
  slider.addEventListener('input', update);
  presets.forEach(button => button.addEventListener('click', () => {
    slider.value = button.dataset.seN;
    update();
  }));
  update();
  panel.hidden = false;
})();

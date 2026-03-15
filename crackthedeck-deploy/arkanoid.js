/* ===== CrackTheDeck — Arkanoid Landing Game ===== */
(function () {
  const canvas = document.getElementById('arkanoidGame');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // --- Responsive sizing ---
  const container = document.getElementById('arkanoidBlock');
  function calcSize() {
    const maxW = Math.min(container ? container.clientWidth : 500, 500);
    const scale = maxW / 249;
    return { scale, W: Math.round(249 * scale), H: Math.round(179 * scale) };
  }
  let { scale: S, W, H } = calcSize();
  canvas.width = W;
  canvas.height = H;

  function onResize() {
    const sz = calcSize();
    S = sz.scale; W = sz.W; H = sz.H;
    canvas.width = W; canvas.height = H;
    if (paddle) {
      paddle.w = W * 0.28;
      paddle.h = 14 * S;
      paddle.y = H - 22 * S;
    }
    if (ball) ball.r = 3 * S;
    rebuildBricks();
  }
  window.addEventListener('resize', onResize);

  // --- Theme-aware palette ---
  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  function buildPalette() {
    const dark = getTheme() === 'dark';
    return {
      bg:      dark ? '#18181f' : '#F0F0F2',
      grid:    dark ? '#1e1e26' : '#E4E4E7',
      primary: dark ? '#00E5C3' : '#00BFA5',
      glow:    dark ? '#00E676' : '#00C853',
      accent:  '#FFD600',
      error:   dark ? '#FF4081' : '#DC2626',
      text:    dark ? '#fff' : '#18181B',
      textMuted: dark ? '#555' : '#A1A1AA',
      brickLabel: dark ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.45)',
      paddleEdge: dark ? '#006E5A' : '#009688',
      paddleLabel: dark ? '#fff' : '#fff',
      ballTrail: dark ? 'rgba(0,229,195,' : 'rgba(0,191,165,',
      ballGlow:  dark ? 'rgba(0,229,195,0.12)' : 'rgba(0,191,165,0.10)',
    };
  }

  let C = buildPalette();

  function getRowColors() {
    const dark = getTheme() === 'dark';
    return dark
      ? ['#00E5C3', '#00CDB0', '#00B59D']
      : ['#00BFA5', '#00AB93', '#009688'];
  }

  // Watch for theme changes
  const observer = new MutationObserver(() => {
    C = buildPalette();
    const rc = getRowColors();
    for (const b of bricks) {
      if (!b.funded) {
        const row = Math.floor(bricks.indexOf(b) / COLS);
        b.color = rc[row] || rc[0];
      }
    }
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // --- Brick layout ---
  const COLS = 5;
  const ROWS = 3;
  const BRICK_LABELS = [
    ['Problem', 'Solution', 'Market', 'Model', 'Team'],
    ['Traction', 'Financials', 'Compete', 'Ask', 'Vision'],
    ['Product', 'Moat', 'GTM', 'Timing', 'Exit'],
  ];

  function brickLayout() {
    const PAD = 3 * S;
    const SIDE_PAD = 6 * S;
    const TOP_PAD = 12 * S;
    const BRICK_W = (W - SIDE_PAD * 2 - (COLS - 1) * PAD) / COLS;
    const BRICK_H = 22 * S;
    return { PAD, SIDE_PAD, TOP_PAD, BRICK_W, BRICK_H };
  }

  // --- Particles ---
  const particles = [];
  class Particle {
    constructor(x, y, color, big) {
      this.x = x; this.y = y;
      const angle = Math.random() * Math.PI * 2;
      const speed = big ? (1.5 + Math.random() * 4) * S : (0.5 + Math.random() * 2) * S;
      this.vx = Math.cos(angle) * speed;
      this.vy = Math.sin(angle) * speed;
      this.life = 1.0;
      this.decay = big ? (0.01 + Math.random() * 0.015) : (0.025 + Math.random() * 0.03);
      this.size = (big ? (2 + Math.random() * 3.5) : (1 + Math.random() * 2)) * S;
      this.color = color;
      this.gravity = (big ? 0.03 : 0.02) * S;
      this.star = big && Math.random() > 0.5;
    }
    update() {
      this.x += this.vx; this.y += this.vy;
      this.vy += this.gravity; this.life -= this.decay;
    }
    draw(ctx) {
      if (this.life <= 0) return;
      ctx.save();
      ctx.globalAlpha = this.life;
      ctx.fillStyle = this.color;
      if (this.star) {
        ctx.translate(this.x, this.y);
        ctx.rotate(this.life * 4);
        ctx.beginPath();
        for (let i = 0; i < 5; i++) {
          const a = (i * 4 * Math.PI) / 5 - Math.PI / 2;
          const r = i % 2 === 0 ? this.size : this.size * 0.4;
          ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
        }
        ctx.closePath(); ctx.fill();
      } else {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size * this.life, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  function burstParticles(x, y, w, h, color, count) {
    const cx = x + w / 2, cy = y + h / 2;
    for (let i = 0; i < count; i++) {
      particles.push(new Particle(cx + (Math.random()-0.5)*w, cy + (Math.random()-0.5)*h, color, false));
    }
  }

  // --- Coins system ---
  const coins = [];
  function spawnCoins(x, y, w, h) {
    const cx = x + w / 2, cy = y + h / 2;
    for (let i = 0; i < 12; i++) {
      const angle = -Math.PI * 0.15 - Math.random() * Math.PI * 0.7;
      const speed = (2 + Math.random() * 3) * S;
      coins.push({
        x: cx + (Math.random()-0.5) * w * 0.5,
        y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        gravity: 0.08 * S,
        life: 1.0,
        decay: 0.008 + Math.random() * 0.006,
        size: (4 + Math.random() * 3) * S,
        rotation: Math.random() * Math.PI * 2,
        rotSpeed: 3 + Math.random() * 5,
      });
    }
    const colors = [C.accent, '#FFE082', '#FFF9C4', '#fff'];
    for (let i = 0; i < 20; i++) {
      particles.push(new Particle(cx, cy, colors[Math.floor(Math.random()*colors.length)], true));
    }
  }

  function updateCoins() {
    for (let i = coins.length - 1; i >= 0; i--) {
      const c = coins[i];
      c.x += c.vx; c.y += c.vy;
      c.vy += c.gravity;
      c.rotation += c.rotSpeed * 0.02;
      c.life -= c.decay;
      if (c.life <= 0) coins.splice(i, 1);
    }
  }

  function drawCoins() {
    for (const c of coins) {
      if (c.life <= 0) continue;
      ctx.save();
      ctx.globalAlpha = c.life;
      ctx.translate(c.x, c.y);
      const scaleX = Math.abs(Math.sin(c.rotation));
      ctx.scale(scaleX < 0.15 ? 0.15 : scaleX, 1);
      ctx.beginPath();
      ctx.arc(0, 0, c.size, 0, Math.PI * 2);
      ctx.fillStyle = C.accent;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(0, 0, c.size * 0.6, 0, Math.PI * 2);
      ctx.fillStyle = '#FFB300';
      ctx.fill();
      ctx.fillStyle = '#000';
      ctx.font = `700 ${Math.round(c.size * 1.1)}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('$', 0, 0.5);
      ctx.restore();
    }
  }

  // --- Floating text ---
  const floats = [];
  function spawnFloat(x, y, text, color, size) {
    floats.push({ x, y, text, color, size: size * S, life: 1.0, vy: -1.0 * S });
  }

  // --- Shockwave ---
  const shockwaves = [];
  function spawnShockwave(x, y) {
    shockwaves.push({ x, y, radius: 0, life: 1.0 });
  }

  let flashAlpha = 0;
  let screenShake = 0;

  // --- Game state ---
  let bricks = [];
  let ball, paddle;
  let round = 0;

  function rebuildBricks() {
    const { PAD, SIDE_PAD, TOP_PAD, BRICK_W, BRICK_H } = brickLayout();
    const rc = getRowColors();
    for (let i = 0; i < bricks.length; i++) {
      const r = Math.floor(i / COLS);
      const c = i % COLS;
      bricks[i].x = SIDE_PAD + c * (BRICK_W + PAD);
      bricks[i].y = TOP_PAD + r * (BRICK_H + PAD);
      bricks[i].w = BRICK_W;
      bricks[i].h = BRICK_H;
    }
  }

  function initBricks() {
    bricks = [];
    const { PAD, SIDE_PAD, TOP_PAD, BRICK_W, BRICK_H } = brickLayout();
    const rc = getRowColors();
    const luckyIdx = Math.floor(Math.random() * COLS * ROWS);
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const idx = r * COLS + c;
        bricks.push({
          x: SIDE_PAD + c * (BRICK_W + PAD),
          y: TOP_PAD + r * (BRICK_H + PAD),
          w: BRICK_W, h: BRICK_H,
          alive: true,
          lucky: idx === luckyIdx,
          color: rc[r],
          opacity: 1,
          dying: false,
          funded: false,
          deathTimer: 0,
          fundedTimer: 0,
          fundedScale: 1,
          glowVal: 0,
          label: BRICK_LABELS[r][c],
        });
      }
    }
  }

  function initBall() {
    const speed = W * 0.008;
    const angle = -Math.PI / 3 + Math.random() * Math.PI / 6;
    ball = {
      x: W / 2 + (Math.random() - 0.5) * 30 * S,
      y: H * 0.55,
      r: 3 * S,
      dx: speed * Math.sin(angle),
      dy: -speed * Math.cos(angle),
      speed,
      trail: [],
    };
  }

  function initPaddle() {
    paddle = { x: W / 2, y: H - 22 * S, w: W * 0.28, h: 14 * S, targetX: W / 2 };
  }

  // --- Update ---
  function findTargetBrick() {
    let best = null, bestScore = -1;
    for (const b of bricks) {
      if (!b.alive || b.dying || b.funded) continue;
      const score = b.y + b.h;
      if (score > bestScore) { bestScore = score; best = b; }
    }
    return best;
  }

  function updatePaddle() {
    if (ball.dy > 0) {
      const tb = findTargetBrick();
      if (tb) {
        const brickCx = tb.x + tb.w / 2;
        const offset = (ball.x - brickCx) * 0.3;
        const clamped = Math.max(-paddle.w * 0.35, Math.min(paddle.w * 0.35, offset));
        paddle.targetX = ball.x + clamped;
      } else {
        paddle.targetX = ball.x;
      }
    } else {
      paddle.targetX = ball.x + ball.dx * 8;
    }
    paddle.targetX = Math.max(paddle.w/2, Math.min(W - paddle.w/2, paddle.targetX));
    paddle.x += (paddle.targetX - paddle.x) * 0.15;
  }

  function updateBall() {
    ball.trail.push({ x: ball.x, y: ball.y });
    if (ball.trail.length > 8) ball.trail.shift();

    ball.x += ball.dx; ball.y += ball.dy;

    if (ball.x - ball.r < 0) { ball.x = ball.r; ball.dx = Math.abs(ball.dx); }
    if (ball.x + ball.r > W) { ball.x = W - ball.r; ball.dx = -Math.abs(ball.dx); }
    if (ball.y - ball.r < 0) { ball.y = ball.r; ball.dy = Math.abs(ball.dy); }
    if (ball.y + ball.r > H) { ball.y = H - ball.r; ball.dy = -Math.abs(ball.dy); }

    // Paddle collision
    if (ball.dy > 0 &&
        ball.y + ball.r >= paddle.y && ball.y + ball.r <= paddle.y + paddle.h + 5 * S &&
        ball.x >= paddle.x - paddle.w/2 - 2 * S && ball.x <= paddle.x + paddle.w/2 + 2 * S) {
      ball.dy = -Math.abs(ball.dy);
      let hit = (ball.x - paddle.x) / (paddle.w / 2);
      if (Math.abs(hit) < 0.15) hit = (hit >= 0 ? 0.15 : -0.15) * (1 + Math.random() * 0.5);
      ball.dx = ball.speed * hit * 0.85;
      const spd = Math.sqrt(ball.dx**2 + ball.dy**2);
      const sc = ball.speed / spd;
      ball.dx *= sc; ball.dy *= sc;
    }

    // Brick collision
    for (const b of bricks) {
      if (!b.alive || b.dying || b.funded) continue;
      if (ball.x + ball.r > b.x && ball.x - ball.r < b.x + b.w &&
          ball.y + ball.r > b.y && ball.y - ball.r < b.y + b.h) {
        const oL = ball.x + ball.r - b.x;
        const oR = b.x + b.w - (ball.x - ball.r);
        const oT = ball.y + ball.r - b.y;
        const oB = b.y + b.h - (ball.y - ball.r);
        const m = Math.min(oL, oR, oT, oB);
        if (m === oT || m === oB) ball.dy = -ball.dy;
        else ball.dx = -ball.dx;

        if (b.lucky) {
          b.funded = true;
          b.fundedTimer = 2.5;
          b.glowVal = 1;
          b.flashTimer = 1.0;
          spawnCoins(b.x, b.y, b.w, b.h);
          spawnShockwave(b.x + b.w/2, b.y + b.h/2);
          spawnFloat(b.x + b.w/2, b.y - 8 * S, 'FUNDED!', C.accent, 14);
          flashAlpha = 0.2;
          screenShake = 6 * S;
        } else {
          b.dying = true;
          b.deathTimer = 1;
          burstParticles(b.x, b.y, b.w, b.h, C.error, 8);
          spawnFloat(b.x + b.w/2, b.y - 4 * S, 'REJECTED', C.error, 9);
          screenShake = Math.max(screenShake, 1.5 * S);
        }
        break;
      }
    }
  }

  function updateBricks(dt) {
    for (const b of bricks) {
      if (b.dying) {
        b.deathTimer -= dt * 4;
        b.opacity = Math.max(0, b.deathTimer);
        if (b.deathTimer <= 0) { b.alive = false; b.dying = false; }
      }
      if (b.funded) {
        b.fundedTimer -= dt;
        b.glowVal = Math.max(0, b.fundedTimer / 2.5);
        b.fundedScale = 1 + Math.sin(b.fundedTimer * 6) * 0.05 * b.glowVal;
        if (b.flashTimer > 0) b.flashTimer -= dt * 2;
        if (b.fundedTimer <= 0) { b.alive = false; b.funded = false; }
      }
    }
  }

  function updateParticles() {
    for (let i = particles.length - 1; i >= 0; i--) {
      particles[i].update();
      if (particles[i].life <= 0) particles.splice(i, 1);
    }
  }

  function updateFloats(dt) {
    for (let i = floats.length - 1; i >= 0; i--) {
      floats[i].y += floats[i].vy;
      floats[i].life -= dt * 0.7;
      if (floats[i].life <= 0) floats.splice(i, 1);
    }
  }

  function updateShockwaves(dt) {
    for (let i = shockwaves.length - 1; i >= 0; i--) {
      shockwaves[i].radius += dt * 200 * S;
      shockwaves[i].life -= dt * 2.5;
      if (shockwaves[i].life <= 0) shockwaves.splice(i, 1);
    }
  }

  function checkReset() {
    if (bricks.every(b => !b.alive)) {
      round++;
      initBricks();
      initBall();
    }
  }

  // --- Draw ---
  function drawBg() {
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = C.grid;
    ctx.lineWidth = 0.4;
    const step = 30 * S;
    for (let x = 0; x < W; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  }

  function drawBricks() {
    for (const b of bricks) {
      if (!b.alive && !b.dying && !b.funded) continue;
      ctx.save();

      if (b.funded) {
        const cx = b.x + b.w/2, cy = b.y + b.h/2;
        ctx.globalAlpha = Math.max(0.3, b.glowVal);
        const gr = (20 + b.glowVal * 15) * S;
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, gr);
        g.addColorStop(0, `rgba(255,214,0,${0.35*b.glowVal})`);
        g.addColorStop(1, 'rgba(255,214,0,0)');
        ctx.fillStyle = g;
        ctx.fillRect(cx-gr, cy-gr, gr*2, gr*2);
        ctx.translate(cx, cy); ctx.scale(b.fundedScale, b.fundedScale); ctx.translate(-cx, -cy);
        const flashT = b.flashTimer || 0;
        const flashPulse = Math.sin(flashT * 18) * 0.5 + 0.5;
        ctx.fillStyle = flashT > 0 ? (flashPulse > 0.5 ? C.accent : C.error) : C.accent;
        ctx.shadowColor = flashT > 0 ? (flashPulse > 0.5 ? C.accent : C.error) : C.accent;
        ctx.shadowBlur = 12 * b.glowVal * S;
        ctx.beginPath(); ctx.roundRect(b.x, b.y, b.w, b.h, 3 * S); ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = '#000';
        ctx.font = `800 ${Math.round(9 * S)}px Inter, sans-serif`;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('FUNDED', b.x + b.w/2, b.y + b.h/2 + 0.5 * S);
      } else {
        ctx.globalAlpha = b.opacity;
        ctx.fillStyle = b.color;
        ctx.beginPath(); ctx.roundRect(b.x, b.y, b.w, b.h, 2 * S); ctx.fill();
        ctx.fillStyle = C.brickLabel;
        ctx.font = `700 ${Math.round(8 * S)}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(b.label || 'Startup', b.x + b.w / 2, b.y + b.h / 2 + 0.5 * S);
      }
      ctx.restore();
    }
  }

  function drawBall() {
    for (let i = 0; i < ball.trail.length; i++) {
      const t = ball.trail[i];
      ctx.beginPath();
      ctx.arc(t.x, t.y, ball.r * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = C.ballTrail + (i/ball.trail.length)*0.18 + ')';
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, ball.r * 2.5, 0, Math.PI * 2);
    ctx.fillStyle = C.ballGlow;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2);
    ctx.fillStyle = getTheme() === 'dark' ? '#fff' : '#18181B';
    ctx.fill();
  }

  function drawPaddle() {
    const px = paddle.x - paddle.w/2;
    const g = ctx.createLinearGradient(px, 0, px + paddle.w, 0);
    g.addColorStop(0, C.paddleEdge);
    g.addColorStop(0.5, C.primary);
    g.addColorStop(1, C.paddleEdge);
    ctx.beginPath();
    ctx.roundRect(px, paddle.y, paddle.w, paddle.h, 5 * S);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.save();
    ctx.shadowColor = C.primary;
    ctx.shadowBlur = 8 * S;
    ctx.strokeStyle = C.ballTrail + '0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(px, paddle.y, paddle.w, paddle.h, 5 * S);
    ctx.stroke();
    ctx.restore();
    ctx.fillStyle = C.paddleLabel;
    ctx.font = `800 ${Math.round(8 * S)}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('MARKET', paddle.x, paddle.y + paddle.h / 2 + 0.5 * S);
  }

  function drawParticles() { for (const p of particles) p.draw(ctx); }

  function drawFloats() {
    for (const f of floats) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, f.life);
      ctx.fillStyle = f.color;
      ctx.font = `700 ${f.size}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.shadowColor = f.color;
      ctx.shadowBlur = 6 * S;
      ctx.fillText(f.text, f.x, f.y);
      ctx.restore();
    }
  }

  function drawShockwaves() {
    for (const s of shockwaves) {
      ctx.save();
      ctx.globalAlpha = s.life * 0.35;
      ctx.strokeStyle = C.accent;
      ctx.lineWidth = 1.5 * s.life * S;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
  }

  function drawFlash() {
    if (flashAlpha > 0) {
      ctx.save();
      ctx.globalAlpha = flashAlpha;
      ctx.fillStyle = C.primary;
      ctx.fillRect(0, 0, W, H);
      ctx.restore();
      flashAlpha *= 0.9;
      if (flashAlpha < 0.008) flashAlpha = 0;
    }
  }

  // --- Visibility: pause when off-screen ---
  let running = false;
  const ioObs = new IntersectionObserver((entries) => {
    running = entries[0].isIntersecting;
    if (running) requestAnimationFrame(loop);
  }, { threshold: 0.1 });
  ioObs.observe(canvas);

  // --- Loop ---
  let lastTime = 0;
  function loop(ts) {
    if (!running) return;
    const dt = Math.min((ts - lastTime) / 1000, 0.05);
    lastTime = ts;

    updatePaddle();
    updateBall();
    updateBricks(dt);
    updateParticles();
    updateCoins();
    updateFloats(dt);
    updateShockwaves(dt);
    checkReset();

    ctx.save();
    if (screenShake > 0.3) {
      ctx.translate((Math.random()-0.5)*screenShake, (Math.random()-0.5)*screenShake);
      screenShake *= 0.86;
    } else screenShake = 0;

    drawBg();
    drawShockwaves();
    drawBricks();
    drawBall();
    drawPaddle();
    drawCoins();
    drawParticles();
    drawFloats();
    drawFlash();
    ctx.restore();

    requestAnimationFrame(loop);
  }

  document.fonts.ready.then(() => {
    initBricks();
    initBall();
    initPaddle();
    requestAnimationFrame(loop);
  });
})();

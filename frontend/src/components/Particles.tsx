import { useEffect, useRef } from "react";

const PALETTE = [
  "#f9a8d4", "#67e8f9", "#c4b5fd", "#fed7aa",
  "#6ee7b7", "#f0abfc", "#7dd3fc", "#ffffff",
];

interface P {
  angle: number; dist: number; speed: number;
  size: number; color: string; life: number; maxLife: number; tw: number;
}

/** Hundreds of tiny glowing atoms streaming off the ball in all directions. */
export function Particles({ active, density = 1 }: { active: boolean; density?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let w = 0, h = 0, raf = 0;
    let parts: P[] = [];
    const rand = (a: number, b: number) => a + Math.random() * (b - a);

    const resize = () => {
      const r = canvas.parentElement!.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = r.width; h = r.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement!);

    const spawn = (edge: number): P => ({
      angle: rand(0, Math.PI * 2),
      dist: edge * rand(0.92, 1.05),
      speed: rand(0.15, 0.7),
      size: rand(0.5, 2.1),
      color: PALETTE[(Math.random() * PALETTE.length) | 0],
      life: 0,
      maxLife: rand(90, 260),
      tw: rand(0, Math.PI * 2),
    });

    let t = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      if (document.hidden) return;
      t += 1;
      const cx = w / 2, cy = h / 2;
      const edge = Math.min(w, h) * 0.30;
      const target = Math.floor((active ? 520 : 260) * density);
      while (parts.length < target) parts.push(spawn(edge));

      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      const keep: P[] = [];
      for (const p of parts) {
        p.life += 1;
        p.tw += 0.08;
        p.dist += p.speed;
        if (p.life > p.maxLife || p.dist > Math.min(w, h) * 0.62) continue;
        keep.push(p);
        const fade = 1 - p.life / p.maxLife;
        const twinkle = 0.45 + 0.55 * Math.abs(Math.sin(p.tw));
        const x = cx + Math.cos(p.angle) * p.dist;
        const y = cy + Math.sin(p.angle) * p.dist * 0.94;
        ctx.globalAlpha = fade * twinkle * 0.9;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      parts = keep;
      ctx.globalAlpha = 1;
    };
    tick();
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [active, density]);

  return <canvas ref={ref} className="pointer-events-none absolute inset-0 h-full w-full" />;
}

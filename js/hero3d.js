/* =========================================================
   NYOS — hero3d.js
   Sphère de particules WebGL (Three.js) + icosaèdre filaire.
   Progressive enhancement : si WebGL ou le module échoue,
   le halo CSS du hero reste seul et rien ne casse.
   ========================================================= */
import * as THREE from './vendor/three.module.min.js';

const mount = document.getElementById('heroCanvas');
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (mount && !REDUCED) init(mount);

function init(mount) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (e) {
    return; // pas de WebGL : on laisse le halo CSS
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
  camera.position.set(0, 0, 6.4);

  renderer.setClearAlpha(0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  mount.appendChild(renderer.domElement);

  /* ---------- géométrie : sphère de Fibonacci ---------- */
  const COUNT = window.innerWidth < 760 ? 3600 : 8000;
  const positions = new Float32Array(COUNT * 3);
  const scales = new Float32Array(COUNT);
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < COUNT; i++) {
    const y = 1 - (i / (COUNT - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;
    positions[i * 3]     = Math.cos(theta) * r * 1.62;
    positions[i * 3 + 1] = y * 1.62;
    positions[i * 3 + 2] = Math.sin(theta) * r * 1.62;
    scales[i] = 0.4 + Math.random() * 1.2;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));

  /* ---------- shaders ---------- */
  const NOISE = `
    vec3 mod289(vec3 x){return x - floor(x*(1.0/289.0))*289.0;}
    vec4 mod289(vec4 x){return x - floor(x*(1.0/289.0))*289.0;}
    vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
    vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
    float snoise(vec3 v){
      const vec2 C = vec2(1.0/6.0, 1.0/3.0);
      const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
      vec3 i  = floor(v + dot(v, C.yyy));
      vec3 x0 = v - i + dot(i, C.xxx);
      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min(g.xyz, l.zxy);
      vec3 i2 = max(g.xyz, l.zxy);
      vec3 x1 = x0 - i1 + C.xxx;
      vec3 x2 = x0 - i2 + C.yyy;
      vec3 x3 = x0 - D.yyy;
      i = mod289(i);
      vec4 p = permute(permute(permute(
                 i.z + vec4(0.0, i1.z, i2.z, 1.0))
               + i.y + vec4(0.0, i1.y, i2.y, 1.0))
               + i.x + vec4(0.0, i1.x, i2.x, 1.0));
      float n_ = 0.142857142857;
      vec3 ns = n_ * D.wyz - D.xzx;
      vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
      vec4 x_ = floor(j * ns.z);
      vec4 y_ = floor(j - 7.0 * x_);
      vec4 x = x_ * ns.x + ns.yyyy;
      vec4 y = y_ * ns.x + ns.yyyy;
      vec4 h = 1.0 - abs(x) - abs(y);
      vec4 b0 = vec4(x.xy, y.xy);
      vec4 b1 = vec4(x.zw, y.zw);
      vec4 s0 = floor(b0)*2.0 + 1.0;
      vec4 s1 = floor(b1)*2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));
      vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
      vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
      vec3 p0 = vec3(a0.xy, h.x);
      vec3 p1 = vec3(a0.zw, h.y);
      vec3 p2 = vec3(a1.xy, h.z);
      vec3 p3 = vec3(a1.zw, h.w);
      vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
      p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
      vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
      m = m * m;
      return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
    }
  `;

  const uniforms = {
    uTime:    { value: 0 },
    uSize:    { value: 15.0 },
    uMouse:   { value: new THREE.Vector2(0, 0) },
    uScroll:  { value: 0 },
    uColorA:  { value: new THREE.Color('#00E5A0') },
    uColorB:  { value: new THREE.Color('#6E5BFF') }
  };

  const material = new THREE.ShaderMaterial({
    uniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      uniform float uTime;
      uniform float uSize;
      uniform vec2  uMouse;
      uniform float uScroll;
      attribute float aScale;
      varying float vN;
      varying float vDepth;
      ${NOISE}
      void main(){
        vec3 p = position;
        vec3 dir = normalize(p);

        float n1 = snoise(p * 0.85 + vec3(0.0, uTime * 0.11, 0.0));
        float n2 = snoise(p * 2.4 - vec3(uTime * 0.07));
        float disp = n1 * 0.19 + n2 * 0.055;

        // réaction douce à la souris
        vec3 m = vec3(uMouse * 2.6, 1.6);
        float prox = 1.0 - clamp(distance(p, m) / 3.4, 0.0, 1.0);
        disp += prox * prox * 0.30;

        p += dir * disp;
        p *= 1.0 - uScroll * 0.22;

        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uSize * aScale * (1.0 / -mv.z) * 2.4;

        vN = n1 + prox;
        vDepth = -mv.z;
      }
    `,
    fragmentShader: `
      uniform vec3 uColorA;
      uniform vec3 uColorB;
      uniform float uScroll;
      varying float vN;
      varying float vDepth;
      void main(){
        vec2 uv = gl_PointCoord - 0.5;
        float d = length(uv);
        if (d > 0.5) discard;
        float alpha = smoothstep(0.5, 0.02, d);
        vec3 col = mix(uColorA, uColorB, smoothstep(0.45, 1.40, vN));
        float fog = smoothstep(10.5, 3.0, vDepth);
        gl_FragColor = vec4(col, alpha * fog * 0.46 * (1.0 - uScroll * 0.85));
      }
    `
  });

  const points = new THREE.Points(geo, material);
  scene.add(points);
  points.position.y = 0.55;

  /* ---------- icosaèdre filaire ---------- */
  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(1.28, 1)),
    new THREE.LineBasicMaterial({
      color: 0x00e5a0, transparent: true, opacity: 0.10,
      blending: THREE.AdditiveBlending, depthWrite: false
    })
  );
  wire.position.y = 0.55;
  scene.add(wire);

  const wire2 = new THREE.LineSegments(
    new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(2.35, 0)),
    new THREE.LineBasicMaterial({
      color: 0x6e5bff, transparent: true, opacity: 0.07,
      blending: THREE.AdditiveBlending, depthWrite: false
    })
  );
  wire2.position.y = 0.55;
  scene.add(wire2);

  /* ---------- interactions ---------- */
  const mouse = new THREE.Vector2(0, 0);
  const target = new THREE.Vector2(0, 0);

  window.addEventListener('mousemove', e => {
    target.x = (e.clientX / window.innerWidth) * 2 - 1;
    target.y = -((e.clientY / window.innerHeight) * 2 - 1);
  }, { passive: true });

  let scrollNorm = 0;
  window.addEventListener('scroll', () => {
    scrollNorm = Math.min(window.scrollY / Math.max(window.innerHeight, 1), 1);
  }, { passive: true });

  /* ---------- resize ---------- */
  const resize = () => {
    const w = mount.clientWidth || window.innerWidth;
    const h = mount.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w < 760 ? 62 : 46;
    camera.updateProjectionMatrix();
    uniforms.uSize.value = w < 760 ? 11 : 15;
  };
  window.addEventListener('resize', resize);
  resize();

  /* ---------- pause hors écran ---------- */
  let visible = true;
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(
      ([entry]) => { visible = entry.isIntersecting; },
      { threshold: 0 }
    ).observe(mount);
  }

  /* ---------- boucle ---------- */
  const clock = new THREE.Clock();
  const loop = () => {
    requestAnimationFrame(loop);
    if (!visible || document.hidden) return;

    const t = clock.getElapsedTime();
    mouse.lerp(target, 0.055);

    uniforms.uTime.value = t;
    uniforms.uMouse.value.set(mouse.x, mouse.y);
    uniforms.uScroll.value += (scrollNorm - uniforms.uScroll.value) * 0.08;

    points.rotation.y = t * 0.045 + mouse.x * 0.32;
    points.rotation.x = mouse.y * -0.22;

    wire.rotation.y = -t * 0.09 + mouse.x * 0.2;
    wire.rotation.x = t * 0.05;
    wire2.rotation.y = t * 0.035 - mouse.x * 0.15;
    wire2.rotation.z = -t * 0.028;

    const s = 1 - uniforms.uScroll.value * 0.25;
    wire.scale.setScalar(s);
    wire2.scale.setScalar(s);
    wire.material.opacity = 0.10 * (1 - uniforms.uScroll.value);
    wire2.material.opacity = 0.07 * (1 - uniforms.uScroll.value);

    renderer.render(scene, camera);
  };
  loop();
}

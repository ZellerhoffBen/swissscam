import { useEffect, useRef } from "react";

const vertexShader = `
  attribute vec2 a_position;
  void main() { gl_Position = vec4(a_position, 0.0, 1.0); }
`;

const fragmentShader = `
  precision highp float;
  uniform vec2 u_resolution;
  uniform float u_time;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), u.x),
      mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x), u.y);
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
      value += amplitude * noise(p);
      p = mat2(0.76, -0.64, 0.64, 0.76) * p * 2.03 + 4.17;
      amplitude *= 0.5;
    }
    return value;
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / max(u_resolution.xy, vec2(1.0));
    vec2 p = (gl_FragCoord.xy * 2.0 - u_resolution.xy) /
      max(min(u_resolution.x, u_resolution.y), 1.0);
    float t = u_time;
    vec2 q = p;
    q.x += sin(q.y * 2.0 + t * 0.16) * 0.22;
    q.y += cos(q.x * 1.7 - t * 0.13) * 0.16;

    float veilA = smoothstep(0.72, 0.04, abs(q.y + sin(q.x * 1.8 + t * 0.22) * 0.32));
    float veilB = smoothstep(0.62, 0.02, abs(q.y * 0.85 - cos(q.x * 2.4 - t * 0.18) * 0.24));
    float veilC = smoothstep(0.48, 0.0, abs(q.y - sin(q.x * 3.2 - t * 0.11) * 0.14));
    float grain = fbm(q * 2.5 + t * 0.035);

    vec3 base = vec3(0.985, 0.99, 1.0);
    vec3 blue = vec3(0.03, 0.42, 0.86);
    vec3 magenta = vec3(0.69, 0.0, 0.43);
    vec3 red = vec3(0.86, 0.0, 0.09);
    vec3 color = base;
    color = mix(color, blue, veilA * 0.025);
    color = mix(color, magenta, veilB * 0.012);
    color = mix(color, red, veilC * 0.006);
    color += (grain - 0.5) * 0.006;
    color *= 0.995 + 0.005 * sin(uv.y * 3.14 + t * 0.1);
    gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
  }
`;

function createShader(gl, type, source) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl) {
  const vertex = createShader(gl, gl.VERTEX_SHADER, vertexShader);
  const fragment = createShader(gl, gl.FRAGMENT_SHADER, fragmentShader);
  if (!vertex || !fragment) return null;
  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  return gl.getProgramParameter(program, gl.LINK_STATUS) ? program : null;
}

export function ShaderBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const gl = canvas?.getContext("webgl", { alpha: false, antialias: false, powerPreference: "low-power" });
    if (!canvas || !gl) return undefined;

    const program = createProgram(gl);
    const buffer = gl.createBuffer();
    if (!program || !buffer) return undefined;
    const resolutionLocation = gl.getUniformLocation(program, "u_resolution");
    const timeLocation = gl.getUniformLocation(program, "u_time");
    const positionLocation = gl.getAttribLocation(program, "a_position");
    let frame = 0;

    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.useProgram(program);
    gl.enableVertexAttribArray(positionLocation);
    gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 1.25);
      canvas.width = Math.max(1, Math.floor(canvas.clientWidth * ratio));
      canvas.height = Math.max(1, Math.floor(canvas.clientHeight * ratio));
      gl.viewport(0, 0, canvas.width, canvas.height);
    };

    const render = (now) => {
      resize();
      gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
      gl.uniform1f(timeLocation, reducedMotion ? 12 : now * 0.001);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!reducedMotion) frame = requestAnimationFrame(render);
    };

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    render(0);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, []);

  return <canvas ref={canvasRef} className="shader-background" aria-hidden="true" />;
}
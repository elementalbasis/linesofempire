#version 330

in vec2 in_pos;

uniform vec2 u_viewport;
uniform float u_zoom;

void main() {
	vec2 ndc = vec2(
			2.0 * u_zoom * in_pos.x / u_viewport.x,
			2.0 * u_zoom * in_pos.y / u_viewport.y
		       );

	gl_Position = vec4(ndc, 0.0, 1.0);
}

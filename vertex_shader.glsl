#version 330

in vec3 in_pos;

uniform vec3 u_east;
uniform vec3 u_north;
uniform vec3 u_forward;
uniform vec2 u_viewport;
uniform float u_zoom;

out float v_depth;

void main() {
	vec3 camera = vec3(
			dot(in_pos, u_east),
			dot(in_pos, u_north),
			dot(in_pos, u_forward)
			);

	v_depth = camera.z;

	vec2 ndc = vec2(
			2.0 * u_zoom * camera.x / u_viewport.x,
			2.0 * u_zoom * camera.y / u_viewport.y
		       );

	gl_Position = vec4(ndc, 0.0, 1.0);
}

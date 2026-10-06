#version 330

in vec2 in_pos;

//uniform vec2 u_viewport;
//uniform float u_zoom;

layout(std140) uniform Camera {
	vec4 camera_east;
	vec4 camera_north;
	vec4 camera_forward;
	vec4 camera_view;
};

void main() {
	vec2 viewport = camera_view.xy;
	float zoom = camera_view.z;
	vec2 ndc = vec2(
			2.0 * zoom * in_pos.x / viewport.x,
			2.0 * zoom * in_pos.y / viewport.y
		       );

	gl_Position = vec4(ndc, 0.0, 1.0);
}

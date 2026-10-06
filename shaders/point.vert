#version 330 core

in vec3 in_pos;

layout(std140) uniform Camera {
	vec4 camera_east;
	vec4 camera_north;
	vec4 camera_forward;
	vec4 camera_screen;
};

uniform float u_point_size;

void main() {
	vec3 p = normalize(in_pos);

	float x = dot(p, camera_east.xyz);
	float y = dot(p, camera_north.xyz);

	float width = camera_screen.x;
	float height = camera_screen.y;
	float zoom = camera_screen.z;

	gl_Position = vec4(
			2.0 * zoom * x / width,
			2.0 * zoom * y / height,
			0.0,
			1.0
			);
	gl_ClipDistance[0] = dot(p, camera_forward.xyz);
	gl_PointSize = u_point_size;
}

#version 330 core

in vec3 in_pos;
in vec2 in_uv;

out vec2 v_uv;

layout(std140) uniform Camera {
	vec4 camera_east;
	vec4 camera_north;
	vec4 camera_forward;
	vec4 camera_screen;
};

void main() {
	float x = dot(in_pos, camera_east.xyz);
	float y = dot(in_pos, camera_north.xyz);
	float z = dot(in_pos, camera_forward.xyz);

	float width = camera_screen.x;
	float height = camera_screen.y;
	float zoom = camera_screen.z;

	gl_Position = vec4(
			2.0 * zoom * x / width,
			2.0 * zoom * y / height,
			0.0,
			1.0
	);

	gl_ClipDistance[0] = z;

	v_uv = in_uv;
}

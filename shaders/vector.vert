#version 330 core

in vec3 in_pos;

out VS_OUT {
	vec3 world_pos;
} vs_out;

void main() {
	vs_out.world_pos = in_pos;

	gl_Position = vec4(in_pos, 1.0);
}

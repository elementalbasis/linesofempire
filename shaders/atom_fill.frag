#version 330

uniform vec3 u_color;
uniform float u_opacity;

out vec4 frag_color;

void main() {
    frag_color = vec4(u_color, u_opacity);
}

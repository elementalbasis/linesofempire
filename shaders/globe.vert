#version 330

in vec3 in_pos;

layout (std140) uniform Camera {
	vec4 camera_east;
	vec4 camera_north;
	vec4 camera_forward;
	vec4 camera_view;
};

out vec3 v_camera;

void main() {
    v_camera = vec3(
        dot(in_pos, camera_east.xyz),
        dot(in_pos, camera_north.xyz),
        dot(in_pos, camera_forward.xyz)
    );

    vec2 viewport = camera_view.xy;
    float zoom = camera_view.z;

    vec2 ndc = vec2(
        2.0 * zoom * v_camera.x / viewport.x,
        2.0 * zoom * v_camera.y / viewport.y
    );

    gl_Position = vec4(ndc, 0.0, 1.0);

    // Used when GL_CLIP_DISTANCE0 is enabled for line geometry
    gl_ClipDistance[0] = v_camera.z;
}

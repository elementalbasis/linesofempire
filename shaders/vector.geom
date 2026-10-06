# version 330 core

layout(lines) in;
layout(line_strip, max_vertices = 64) out;

// World-space sphere coordinates passed by vector.vert
in VS_OUT {
	vec3 world_pos;
} gs_in[];

layout(std140) uniform Camera {
	vec4 camera_east;
	vec4 camera_north;
	vec4 camera_forward;
	vec4 camera_screen;
};

uniform float u_max_arc;

// Project a point on the unit sphere into screen coordinates
vec4 project_point(vec3 p) {
	float x = dot(p, camera_east.xyz);
	float y = dot(p, camera_north.xyz);

	float width = camera_screen.x;
	float height = camera_screen.y;
	float zoom = camera_screen.z;

	return vec4(
			2.0 * zoom * x / width,
			2.0 * zoom * y / height,
			0.0,
			1.0
		   );
}

// Spherical linear interpolation along the shorter great-circle arc
vec3 slerp(vec3 a, vec3 b, float t) {
	float cosine = clamp(dot(a, b), -1.0, 1.0);
	float angle = acos(cosine);
	float sine = sin(angle);

	if (angle < 1e-6) {
		return a;
	}

	if (abs(sine) < 1e-6) {
		return normalize(mix(a, b, t));
	}

	return normalize(
			sin((1.0 - t) * angle) / sine * a
			+ sin(t * angle) / sine * b
			);
}

void main() {
	vec3 a = normalize(gs_in[0].world_pos);
	vec3 b = normalize(gs_in[1].world_pos);

	float angle = acos(clamp(dot(a, b), -1.0, 1.0));

	int segments = max(1, int(ceil(angle / u_max_arc)));
	segments = min(segments, 63);

	for (int i = 0; i <= segments; ++i) {
		float t = float(i) / float(segments);

		vec3 p = slerp(a, b, t);

		float camera_z = dot(p, camera_forward.xyz);

		gl_ClipDistance[0] = camera_z;
		gl_Position = project_point(p);

		EmitVertex();
	}

	EndPrimitive();
}

#version 330

layout(triangles) in;
layout(triangle_strip, max_vertices = 32) out;

in vec3 v_camera[];

layout(std140) uniform Camera {
	vec4 camera_east;
	vec4 camera_north;
	vec4 camera_forward;
	vec4 camera_view;
};

//uniform vec2 u_viewport;
//uniform float u_zoom;

const float PI = 3.14159265358979323846;
const float TAU = 6.28318530717958647692;

const int MAX_ARC_SEGMENTS = 8;
const float ARC_STEP = 0.0872664626;  // 5 degrees


vec4 project_point(vec3 p) {
	vec2 viewport = camera_view.xy;
	float zoom = camera_view.z;
	vec2 ndc = vec2(
		2.0 * zoom * p.x / viewport.x,
		2.0 * zoom * p.y / viewport.y
	);

	return vec4(ndc, 0.0, 1.0);
}


void emit_point(vec3 p) {
	gl_Position = project_point(p);
	EmitVertex();
}


void emit_triangle(vec3 a, vec3 b, vec3 c) {
	emit_point(a);
	emit_point(b);
	emit_point(c);
	EndPrimitive();
}


vec3 horizon_intersection(vec3 a, vec3 b) {
	// a and b are on opposite sides of z = 0.
	float t = a.z / (a.z - b.z);

	vec3 p = mix(a, b, t);

	// Put the intersection exactly on the unit horizon circle.
	vec2 xy = normalize(p.xy);

	return vec3(xy, 0.0);
}


float shortest_angle(float a, float b) {
	float delta = b - a;

	if (delta > PI)
		delta -= TAU;

	if (delta < -PI)
		delta += TAU;

	return delta;
}


vec3 horizon_point(float angle) {
	return vec3(
		cos(angle),
		sin(angle),
		0.0
	);
}


void emit_horizon_fan(
	vec3 anchor,
	vec3 start,
	vec3 finish
) {
	float a0 = atan(start.y, start.x);
	float a1 = atan(finish.y, finish.x);

	float delta = shortest_angle(a0, a1);

	int segments = int(ceil(abs(delta) / ARC_STEP));
	segments = clamp(segments, 1, MAX_ARC_SEGMENTS);

	vec3 previous = start;

	for (int i = 1; i <= MAX_ARC_SEGMENTS; ++i) {
		if (i > segments)
			break;

		float t = float(i) / float(segments);

		vec3 next;

		if (i == segments) {
			next = finish;
		} else {
			next = horizon_point(a0 + delta * t);
		}

		emit_triangle(
			anchor,
			previous,
			next
		);

		previous = next;
	}
}


void main() {
	vec3 a = v_camera[0];
	vec3 b = v_camera[1];
	vec3 c = v_camera[2];

	bool va = a.z >= 0.0;
	bool vb = b.z >= 0.0;
	bool vc = c.z >= 0.0;

	int visible = int(va) + int(vb) + int(vc);
	/*
	if (va) visible++;
	if (vb) visible++;
	if (vc) visible++;
	*/

	// Completely hidden.
	if (visible == 0) {
		return;
	}


	// Completely visible.
	if (visible == 3) {
		emit_triangle(a, b, c);
		return;
	}


	// Exactly one vertex is visible.
	if (visible == 1) {
		vec3 front;
		vec3 back1;
		vec3 back2;

		if (va) {
			front = a;
			back1 = b;
			back2 = c;
		} else if (vb) {
			front = b;
			back1 = c;
			back2 = a;
		} else {
			front = c;
			back1 = a;
			back2 = b;
		}

		vec3 p = horizon_intersection(front, back1);
		vec3 q = horizon_intersection(front, back2);

		emit_horizon_fan(front, p, q);

		return;
	}


	// Exactly two vertices are visible.
	vec3 front1;
	vec3 front2;
	vec3 back;

	if (!va) {
		back = a;
		front1 = b;
		front2 = c;
	} else if (!vb) {
		back = b;
		front1 = c;
		front2 = a;
	} else {
		back = c;
		front1 = a;
		front2 = b;
	}

	vec3 p = horizon_intersection(front1, back);
	vec3 q = horizon_intersection(front2, back);

	// Interior portion away from the horizon.
	emit_triangle(front1, front2, q);

	// Curved portion against the horizon.
	emit_horizon_fan(front1, q, p);
}

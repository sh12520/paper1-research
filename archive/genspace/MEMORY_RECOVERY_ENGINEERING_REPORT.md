# MEMORY-RECOVERY-ENGINEERING-01

Status: BLOCKED

Fixed plan: 32 ENGINEERING instances, family × richness × depth × two fixed indices; pressure medium and conflict high.
No SMOKE/PILOT/CONFIRM seed or instance used.
Exact non-timing output equality: 32/32 compared, 32 required.
Batch children exited and RSS reclaimed: False. Strictly monotonically declining available memory at child exits: False.
Total wall time: 58.98 s.
0.2-second periodic process-level samples matched to instance boundary events; evaluation_complete observer occurs immediately after evaluator returns; internal evaluator stage boundaries not instrumented. RSS peaks use OS PeakWorkingSetSize. Child reclamation inferred from observed process exit and unavailable/zero working-set access; system available memory can change concurrently due to unrelated processes and does not prove bytewise recovery.

```json
{
  "long": {
    "indexes": [
      0,
      1,
      2,
      3,
      4,
      5,
      6,
      7,
      8,
      9,
      10,
      11,
      12,
      13,
      14,
      15,
      16,
      17,
      18,
      19,
      20,
      21,
      22,
      23,
      24,
      25,
      26,
      27,
      28,
      29,
      30,
      31
    ],
    "returncode": 0,
    "memory_guard": false,
    "seconds": 19.65599999999995,
    "samples": 100,
    "exit": {
      "t": 1794901609.052028,
      "event": "child_exit",
      "worker_rss": 32768,
      "worker_peak": 697225216,
      "orchestrator_rss": 27103232,
      "system_used": 14192304128,
      "system_available": 2716762112,
      "phase": "long",
      "indexes": [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31
      ],
      "process_exited": true,
      "exit_code": 0
    }
  },
  "batches": [
    {
      "indexes": [
        0,
        1,
        2,
        3
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 4.625,
      "samples": 25,
      "exit": {
        "t": 1794901613.6773272,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 525070336,
        "orchestrator_rss": 27115520,
        "system_used": 14120431616,
        "system_available": 2788634624,
        "phase": "batch",
        "indexes": [
          0,
          1,
          2,
          3
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        4,
        5,
        6,
        7
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 5.8279999999999745,
      "samples": 31,
      "exit": {
        "t": 1794901619.509518,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 694308864,
        "orchestrator_rss": 27123712,
        "system_used": 14211850240,
        "system_available": 2697216000,
        "phase": "batch",
        "indexes": [
          4,
          5,
          6,
          7
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        8,
        9,
        10,
        11
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 4.4220000000000255,
      "samples": 24,
      "exit": {
        "t": 1794901623.9330025,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 563736576,
        "orchestrator_rss": 27205632,
        "system_used": 14132711424,
        "system_available": 2776354816,
        "phase": "batch",
        "indexes": [
          8,
          9,
          10,
          11
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        12,
        13,
        14,
        15
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 4.641000000000076,
      "samples": 25,
      "exit": {
        "t": 1794901628.5596166,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 559308800,
        "orchestrator_rss": 27205632,
        "system_used": 14182199296,
        "system_available": 2726866944,
        "phase": "batch",
        "indexes": [
          12,
          13,
          14,
          15
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        16,
        17,
        18,
        19
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 4.811999999999898,
      "samples": 26,
      "exit": {
        "t": 1794901633.388759,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 620400640,
        "orchestrator_rss": 27205632,
        "system_used": 14100881408,
        "system_available": 2808184832,
        "phase": "batch",
        "indexes": [
          16,
          17,
          18,
          19
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        20,
        21,
        22,
        23
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 5.219000000000051,
      "samples": 28,
      "exit": {
        "t": 1794901638.61486,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 630460416,
        "orchestrator_rss": 27209728,
        "system_used": 14129729536,
        "system_available": 2779336704,
        "phase": "batch",
        "indexes": [
          20,
          21,
          22,
          23
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        24,
        25,
        26,
        27
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 4.625,
      "samples": 25,
      "exit": {
        "t": 1794901643.2422051,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 524648448,
        "orchestrator_rss": 27209728,
        "system_used": 14096445440,
        "system_available": 2812620800,
        "phase": "batch",
        "indexes": [
          24,
          25,
          26,
          27
        ],
        "process_exited": true,
        "exit_code": 0
      }
    },
    {
      "indexes": [
        28,
        29,
        30,
        31
      ],
      "returncode": 0,
      "memory_guard": false,
      "seconds": 5.030999999999949,
      "samples": 27,
      "exit": {
        "t": 1794901648.2721734,
        "event": "child_exit",
        "worker_rss": 32768,
        "worker_peak": 630513664,
        "orchestrator_rss": 27209728,
        "system_used": 14151413760,
        "system_available": 2757652480,
        "phase": "batch",
        "indexes": [
          28,
          29,
          30,
          31
        ],
        "process_exited": true,
        "exit_code": 0
      }
    }
  ],
  "metrics": {
    "long": {
      "instance_end_count": 32,
      "initial_rss": 1998848,
      "final_rss": 465387520,
      "initial_available": 2756050944,
      "final_available": 2262904832,
      "rss_slope_bytes_per_instance": 321077.30205278593,
      "available_slope_bytes_per_instance": -3800466.392961877,
      "peak_worker_rss": 697225216,
      "min_available": 2141589504,
      "exit_available": [
        2716762112
      ],
      "exit_worker_rss": [
        32768
      ],
      "exit_process_exited": [
        true
      ],
      "exit_recoveries": [
        {
          "indexes": [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
            26,
            27,
            28,
            29,
            30,
            31
          ],
          "initial_rss": 1998848,
          "final_rss": 465387520,
          "available_before_exit": 2262904832,
          "available_after_exit": 2716762112,
          "available_change": 453857280
        }
      ]
    },
    "batch": {
      "instance_end_count": 32,
      "initial_rss": 1998848,
      "final_rss": 515252224,
      "initial_available": 2704846848,
      "final_available": 2250776576,
      "rss_slope_bytes_per_instance": -1243377.7360703812,
      "available_slope_bytes_per_instance": 2687742.4985337243,
      "peak_worker_rss": 694308864,
      "min_available": 2072707072,
      "exit_available": [
        2788634624,
        2697216000,
        2776354816,
        2726866944,
        2808184832,
        2779336704,
        2812620800,
        2757652480
      ],
      "exit_worker_rss": [
        32768,
        32768,
        32768,
        32768,
        32768,
        32768,
        32768,
        32768
      ],
      "exit_process_exited": [
        true,
        true,
        true,
        true,
        true,
        true,
        true,
        true
      ],
      "exit_recoveries": [
        {
          "indexes": [
            0,
            1,
            2,
            3
          ],
          "initial_rss": 1998848,
          "final_rss": 411557888,
          "available_before_exit": 2398838784,
          "available_after_exit": 2788634624,
          "available_change": 389795840
        },
        {
          "indexes": [
            4,
            5,
            6,
            7
          ],
          "initial_rss": 1998848,
          "final_rss": 518139904,
          "available_before_exit": 2188660736,
          "available_after_exit": 2697216000,
          "available_change": 508555264
        },
        {
          "indexes": [
            8,
            9,
            10,
            11
          ],
          "initial_rss": 1998848,
          "final_rss": 412581888,
          "available_before_exit": 2374438912,
          "available_after_exit": 2776354816,
          "available_change": 401915904
        },
        {
          "indexes": [
            12,
            13,
            14,
            15
          ],
          "initial_rss": 1998848,
          "final_rss": 452894720,
          "available_before_exit": 2287882240,
          "available_after_exit": 2726866944,
          "available_change": 438984704
        },
        {
          "indexes": [
            16,
            17,
            18,
            19
          ],
          "initial_rss": 1998848,
          "final_rss": 476946432,
          "available_before_exit": 2339291136,
          "available_after_exit": 2808184832,
          "available_change": 468893696
        },
        {
          "indexes": [
            20,
            21,
            22,
            23
          ],
          "initial_rss": 1998848,
          "final_rss": 464531456,
          "available_before_exit": 2326757376,
          "available_after_exit": 2779336704,
          "available_change": 452579328
        },
        {
          "indexes": [
            24,
            25,
            26,
            27
          ],
          "initial_rss": 1998848,
          "final_rss": 36745216,
          "available_before_exit": 2785767424,
          "available_after_exit": 2812620800,
          "available_change": 26853376
        },
        {
          "indexes": [
            28,
            29,
            30,
            31
          ],
          "initial_rss": 1998848,
          "final_rss": 515252224,
          "available_before_exit": 2250776576,
          "available_after_exit": 2757652480,
          "available_change": 506875904
        }
      ]
    }
  }
}
```

## Lifecycle diagnostic and sampling limitation

All eight batch children returned exit code zero. After each `wait`, the audit recorded the still-held process handle and closed its own Popen handle before querying the PID again; all eight post-close queries nevertheless reported 32,768 bytes. Thus the audit's strict zero-or-inaccessible reclamation criterion did not pass. The reason for the remaining accessible exited process object is unresolved. Each corresponding system-available measurement increased on exit, which supports substantial release but cannot establish byte-for-byte reclamation because other processes also affect this metric. The 0.2-second periodic monitor and evaluator-completion event do not guarantee a sample at each evaluator internal critical-stage boundary; this requirement remains unverified. The first attempt and its independent snapshot are archived at `results/memory_recovery_engineering_attempt01_BLOCKED/`.
